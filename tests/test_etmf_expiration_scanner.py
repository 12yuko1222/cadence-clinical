import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from apps.etmf.database import db_manager
from apps.etmf.expiration_scanner import (
    determine_warning_window,
    execute_expiration_scan_cycle,
    start_background_etmf_expiration_scanner,
    stop_background_etmf_expiration_scanner,
)
from apps.etmf.models import Base, DocumentExpirationAlertState, TMFDocument


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Setup in-memory SQLite database before each test and clear down after."""
    db_manager.init_db("sqlite+aiosqlite:///:memory:", echo=False)
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_manager.close()


@pytest.mark.asyncio
async def test_determine_warning_window():
    """Test the threshold helper determine_warning_window on standard thresholds."""
    now = datetime.now(timezone.utc)

    # 1. Past expiration
    assert determine_warning_window(now - timedelta(days=1), now) == "EXPIRED"
    assert determine_warning_window(now, now) == "EXPIRED"

    # 2. Within 7 days
    # exactly 7 days
    assert determine_warning_window(now + timedelta(days=7), now) == "7"
    # just inside 7 days (6.9 days)
    assert determine_warning_window(now + timedelta(days=6.9), now) == "7"
    # just outside 7 days (7.1 days) -> falls into 30
    assert determine_warning_window(now + timedelta(days=7.1), now) == "30"

    # 3. Within 30 days
    assert determine_warning_window(now + timedelta(days=30), now) == "30"
    assert determine_warning_window(now + timedelta(days=29.9), now) == "30"
    assert determine_warning_window(now + timedelta(days=30.1), now) == "90"

    # 4. Within 90 days
    assert determine_warning_window(now + timedelta(days=90), now) == "90"
    assert determine_warning_window(now + timedelta(days=89.9), now) == "90"
    # far outside 90 days
    assert determine_warning_window(now + timedelta(days=91), now) is None


@pytest.mark.asyncio
async def test_execute_expiration_scan_cycle_thresholds():
    """Test that execute_expiration_scan_cycle queries correctly, identifies states, and records alerts."""
    session_maker = db_manager.get_session_maker()
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        # Create documents with various expiration dates
        # d_expired: past expiration
        # d_7: 5 days remaining -> "7"
        # d_30: 20 days remaining -> "30"
        # d_90: 80 days remaining -> "90"
        # d_none: 100 days remaining -> no alert
        # d_no_exp: null expiration -> no alert
        d_expired = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_expired.pdf",
            content="expired",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now - timedelta(days=2),
        )
        d_7 = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_7.pdf",
            content="7",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now + timedelta(days=5),
        )
        d_30 = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_30.pdf",
            content="30",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now + timedelta(days=20),
        )
        d_90 = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_90.pdf",
            content="90",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now + timedelta(days=80),
        )
        d_none = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_none.pdf",
            content="none",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now + timedelta(days=100),
        )
        d_no_exp = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="d_no_exp.pdf",
            content="no_exp",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=None,
        )
        session.add_all([d_expired, d_7, d_30, d_90, d_none, d_no_exp])
        await session.commit()

    # Run scanner cycle
    await execute_expiration_scan_cycle(session_maker)

    # Verify persistent state
    async with session_maker() as session:
        # Check expired
        res = await session.execute(
            select(DocumentExpirationAlertState)
            .join(TMFDocument)
            .where(TMFDocument.filename == "d_expired.pdf")
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "EXPIRED"

        # Check 7
        res = await session.execute(
            select(DocumentExpirationAlertState)
            .join(TMFDocument)
            .where(TMFDocument.filename == "d_7.pdf")
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "7"

        # Check 30
        res = await session.execute(
            select(DocumentExpirationAlertState)
            .join(TMFDocument)
            .where(TMFDocument.filename == "d_30.pdf")
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "30"

        # Check 90
        res = await session.execute(
            select(DocumentExpirationAlertState)
            .join(TMFDocument)
            .where(TMFDocument.filename == "d_90.pdf")
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "90"

        # Check d_none
        res = await session.execute(
            select(DocumentExpirationAlertState)
            .join(TMFDocument)
            .where(TMFDocument.filename == "d_none.pdf")
        )
        assert len(res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_scanner_idempotency_restart_and_rearming():
    """Test scanner idempotency across runs, restart behavior, and explicit re-arming."""
    session_maker = db_manager.get_session_maker()
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        doc = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="idempotent_doc.pdf",
            content="content",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now + timedelta(days=5),
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # 1. Run cycle first time -> creates 1 alert state row
    await execute_expiration_scan_cycle(session_maker)

    async with session_maker() as session:
        res = await session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "7"

    # 2. Run cycle second time -> still only 1 alert state row (no duplicates)
    await execute_expiration_scan_cycle(session_maker)

    async with session_maker() as session:
        res = await session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1

    # 3. Fresh session pointed at the same DB still recognizes prior dedup state
    async with session_maker() as fresh_session:
        res = await fresh_session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        assert len(res.scalars().all()) == 1

    # 4. Explicitly remove/delete the row (re-arm) and rerun -> creates a fresh alert row
    async with session_maker() as session:
        res = await session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        alert = res.scalars().first()
        await session.delete(alert)
        await session.commit()

    # Rerun scanner -> should generate a new alert for "7"
    await execute_expiration_scan_cycle(session_maker)

    async with session_maker() as session:
        res = await session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        alerts = res.scalars().all()
        assert len(alerts) == 1
        assert alerts[0].warning_window == "7"


@pytest.mark.asyncio
async def test_failure_isolation_and_resilience():
    """Test that a loop iteration exception is isolated and the loop keeps running."""
    session_maker = MagicMock()
    # Force the scanner's cycle to raise an exception
    session_maker.side_effect = Exception("Transient DB connectivity loss")

    # Start loop with very short interval
    os.environ["ETMF_EXPIRATION_SCANNER_INTERVAL_SECONDS"] = "0.1"
    await start_background_etmf_expiration_scanner(session_maker, interval=0.1)

    import apps.etmf.expiration_scanner as es

    assert es._scanner_task is not None
    assert es._should_run is True

    # Let it run for a short duration to verify it isolated the exception and did not crash/die
    await asyncio.sleep(0.3)

    assert es._scanner_task is not None
    assert es._should_run is True

    # Stop loop cleanly
    await stop_background_etmf_expiration_scanner()
    assert es._scanner_task is None
    assert es._should_run is False


@pytest.mark.asyncio
async def test_scanner_shutdown_cancellation():
    """Test that background task shuts down cleanly with no leaked background task."""
    session_maker = MagicMock()
    await start_background_etmf_expiration_scanner(session_maker, interval=0.1)

    import apps.etmf.expiration_scanner as es

    assert es._scanner_task is not None
    assert es._should_run is True

    await stop_background_etmf_expiration_scanner()
    assert es._scanner_task is None
    assert es._should_run is False


@pytest.mark.asyncio
async def test_audit_attribution():
    """Verify that alert-state rows created carry the explicit scanner service identity in created_by."""
    session_maker = db_manager.get_session_maker()
    now = datetime.now(timezone.utc)

    async with session_maker() as session:
        doc = TMFDocument(
            study_id="study_1",
            zone=1,
            section="01",
            artifact_type="Protocol",
            filename="audit_attributed.pdf",
            content="content",
            mime_type="application/pdf",
            created_by="test_user",
            expiration_date=now - timedelta(days=1),
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # Run cycle
    await execute_expiration_scan_cycle(session_maker)

    async with session_maker() as session:
        res = await session.execute(
            select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc_id
            )
        )
        alert = res.scalars().one()
        assert alert.created_by == "expiration_scanner"
        assert alert.reason_for_change == "System-initiated expiration alert generation"
