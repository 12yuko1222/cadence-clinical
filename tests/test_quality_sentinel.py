"""Unit & integration test suite for Protocol Quality Sentinel and site feasibility analyzer.

Requirements: PRD-SYS-001
"""

from fastapi.testclient import TestClient

import packages  # noqa: F401
from apps.designer.main import app
from apps.designer.services.quality_sentinel import ProtocolQualitySentinel
from tests.test_synopsis_router import _make_auth_headers

client = TestClient(app)


def test_quality_sentinel_complete_protocol() -> None:
    """Validate evaluating a complete protocol produces a 100.0 quality score.

    Requirements: PRD-SYS-001
    """
    study_payload = {
        "id": "study_complete_001",
        "name": "Complete Study Protocol",
        "studyDesigns": [
            {
                "id": "design_01",
                "objectives": [{"id": "obj_01", "name": "Primary Objective"}],
                "encounters": [{"id": "enc_01"}, {"id": "enc_02"}],
                "activities": [{"id": "act_01"}],
            }
        ],
        "eligibilityCriteria": [
            {"id": "crit_01", "text": "Age >= 18"},
        ],
    }

    sentinel = ProtocolQualitySentinel()
    report = sentinel.evaluate_protocol_quality(study_payload)

    assert report.study_id == "study_complete_001"
    assert report.passed is True
    assert report.quality_score == 100.0
    assert report.patient_burden_index == 5.0  # 2 encounters * 1.5 + 1 act * 2.0 = 5.0
    assert len(report.findings) == 0


def test_quality_sentinel_incomplete_protocol_detects_errors() -> None:
    """Validate incomplete protocol produces ERROR findings and lowers quality score.

    Requirements: PRD-SYS-001
    """
    incomplete_payload = {
        "id": "study_incomplete_002",
        "name": "Incomplete Draft Protocol",
        # Missing studyDesigns, eligibilityCriteria, objectives
    }

    sentinel = ProtocolQualitySentinel()
    report = sentinel.evaluate_protocol_quality(incomplete_payload)

    assert report.study_id == "study_incomplete_002"
    assert report.passed is False
    assert report.quality_score < 100.0
    assert len(report.findings) >= 2  # Structural ERROR + Regulatory WARNING

    finding_ids = [f.rule_id for f in report.findings]
    assert "SENTINEL_STRUCT_01" in finding_ids
    assert "SENTINEL_REG_02" in finding_ids


def test_quality_sentinel_router_endpoint() -> None:
    """Validate POST /api/v1/designer/sentinel/evaluate API endpoint returns report.

    Requirements: PRD-SYS-001
    """
    headers = _make_auth_headers(change_reason="Audit protocol quality sentinel")
    response = client.post(
        "/api/v1/designer/sentinel/evaluate",
        json={
            "id": "study_api_eval_003",
            "name": "API Eval Study",
            "studyDesigns": [
                {
                    "id": "design_main",
                    "objectives": [{"id": "obj_1", "name": "Primary"}],
                }
            ],
            "eligibilityCriteria": [{"id": "c1", "text": "Inclusion"}],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "study_api_eval_003"
    assert data["passed"] is True
    assert data["quality_score"] == 100.0
