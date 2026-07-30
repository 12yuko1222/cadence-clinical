import asyncio
import logging
import os
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select

from apps.etmf.models import DocumentExpirationAlertState, TMFDocument
from packages.security.context import (
    current_change_reason,
    current_user_id,
    service_audit_context,
)

logger = logging.getLogger("etmf-expiration-scanner")

_scanner_task: Optional[asyncio.Task] = None
_should_run: bool = False


def determine_warning_window(
    expiration_date: datetime,
    now: datetime,
    warning_windows: List[int] = [7, 30, 90],
) -> Optional[str]:
    """
    Determines which window (e.g. "90", "30", "7", or "EXPIRED") a document's expiration falls into.
    """
    # Ensure both are timezone-aware datetimes
    if expiration_date.tzinfo is None:
        expiration_date = expiration_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if expiration_date <= now:
        return "EXPIRED"

    remaining_days = (expiration_date - now).total_seconds() / 86400.0  # deid-ignore

    # Smallest warning windows first (tightest threshold)
    sorted_windows = sorted(warning_windows)
    for window in sorted_windows:
        if remaining_days <= window:
            return str(window)

    return None


async def execute_expiration_scan_cycle(session_maker: Any) -> None:
    """
    Runs a single cycle of the document expiration alert scanning.
    Identifies documents approaching or past expiration and persistently records alert states.
    """
    now = datetime.now(timezone.utc)

    # Get warning windows config
    env_windows = os.getenv("ETMF_EXPIRATION_WARNING_WINDOWS")
    if env_windows:
        try:
            warning_windows = [
                int(w.strip()) for w in env_windows.split(",") if w.strip()
            ]
        except ValueError:
            logger.warning(
                "Invalid ETMF_EXPIRATION_WARNING_WINDOWS env value: %s. Using default [7, 30, 90]",
                env_windows,
            )
            warning_windows = [7, 30, 90]
    else:
        warning_windows = [7, 30, 90]

    # Wrap the writes in a service identity context
    service_name = "expiration_scanner"
    change_reason = "System-initiated expiration alert generation"

    async with session_maker() as session:
        # Query candidate TMFDocument rows (non-null expiration_date)
        stmt = select(TMFDocument).where(TMFDocument.expiration_date.isnot(None))
        res = await session.execute(stmt)
        documents = res.scalars().all()

        for doc in documents:
            # expiration_date might be saved as date/datetime. Let's convert if needed.
            doc_expiry = doc.expiration_date
            if isinstance(doc_expiry, date) and not isinstance(doc_expiry, datetime):
                doc_expiry = datetime.combine(doc_expiry, datetime.min.time()).replace(
                    tzinfo=timezone.utc
                )

            window = determine_warning_window(doc_expiry, now, warning_windows)
            if window is None:
                continue

            # Check if alert state already exists for this (document_id, window)
            stmt_alert = select(DocumentExpirationAlertState).where(
                DocumentExpirationAlertState.document_id == doc.id,
                DocumentExpirationAlertState.warning_window == window,
            )
            res_alert = await session.execute(stmt_alert)
            alert_state = res_alert.scalars().first()

            if alert_state is not None:
                # Deduplicated: already alerted for this window
                continue

            # Wrap in audit context for write attribution
            with service_audit_context(service_name, change_reason):
                created_by = current_user_id.get() or service_name
                reason_for_change = current_change_reason.get() or change_reason

                new_alert = DocumentExpirationAlertState(
                    document_id=doc.id,
                    warning_window=window,
                    alerted_at=now.replace(tzinfo=None),  # Naive datetime for DB
                    created_by=created_by,
                    reason_for_change=reason_for_change,
                    version_index=1,
                )

                try:
                    async with session.begin_nested():
                        session.add(new_alert)
                        await session.flush()
                        logger.info(
                            "Generated alert state '%s' for document ID %s",
                            window,
                            doc.id,
                        )
                except Exception as e:
                    # Rely on unique constraint as safety net
                    logger.warning(
                        "Failed to insert alert state due to database safety net: %s",
                        e,
                    )

        await session.commit()


async def start_background_etmf_expiration_scanner(
    session_maker: Any, interval: Optional[float] = None
) -> None:
    """
    Start the asynchronous background eTMF expiration scanner thread.
    """
    global _scanner_task, _should_run
    if interval is None:
        interval = float(
            os.getenv(
                "ETMF_EXPIRATION_SCANNER_INTERVAL_SECONDS", "86400.0"
            )  # deid-ignore
        )
    _should_run = True

    async def scanner_loop():
        logger.info(
            "Background eTMF expiration scanner started with interval %s seconds.",
            interval,
        )
        while _should_run:
            try:
                await execute_expiration_scan_cycle(session_maker)
            except Exception as e:
                logger.error(
                    "Error in eTMF expiration scanner cycle: %s",
                    e,
                    exc_info=True,
                )

            # Chunked sleep for responsive shutdown
            for _ in range(int(interval * 10)):
                if not _should_run:
                    break
                await asyncio.sleep(0.1)

    _scanner_task = asyncio.create_task(scanner_loop())


async def stop_background_etmf_expiration_scanner() -> None:
    """
    Stop the asynchronous background eTMF expiration scanner thread cleanly.
    """
    global _scanner_task, _should_run
    _should_run = False
    if _scanner_task:
        try:
            await _scanner_task
        except asyncio.CancelledError:
            pass
        _scanner_task = None
    logger.info("Background eTMF expiration scanner stopped.")
