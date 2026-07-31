"""Unit & integration test suite for downstream artifact cascade engine.

Requirements: PRD-SYS-001
"""

from fastapi.testclient import TestClient

import packages  # noqa: F401
from apps.designer.main import app
from apps.designer.services.artifact_cascade import ArtifactCascadeEngine
from tests.test_synopsis_router import _make_auth_headers

client = TestClient(app)


def test_artifact_cascade_engine_generation() -> None:
    """Validate cascading USDM study payload generates eCRF forms and SoA structures.

    Requirements: PRD-SYS-001
    """
    study_payload = {
        "id": "study_cascade_101",
        "name": "Cascade Test Study",
        "studyDesigns": [
            {
                "id": "design_01",
                "encounters": [{"id": "enc_1"}, {"id": "enc_2"}],
                "activities": [
                    {"id": "act_vs", "name": "Vital Signs Assessment"},
                    {"id": "act_lb", "name": "Central Lab Blood Draw"},
                ],
            }
        ],
    }

    engine = ArtifactCascadeEngine()
    report = engine.cascade_protocol_to_downstream(study_payload, amendment_version=1)

    assert report.study_id == "study_cascade_101"
    assert report.amendment_version == 1
    assert report.forms_created == 3  # DM + VS + LB
    assert report.visits_created == 2

    domains = [f.domain for f in report.forms]
    assert "DM" in domains
    assert "VS" in domains
    assert "LB" in domains


def test_artifact_cascade_router_endpoint() -> None:
    """Validate POST /api/v1/designer/cascade/propagate API endpoint.

    Requirements: PRD-SYS-001
    """
    headers = _make_auth_headers(change_reason="Propagate cascade artifacts")
    response = client.post(
        "/api/v1/designer/cascade/propagate?amendment_version=2",
        json={
            "id": "study_cascade_102",
            "studyDesigns": [
                {
                    "id": "d1",
                    "activities": [{"id": "a1", "name": "Vital Signs"}],
                }
            ],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["study_id"] == "study_cascade_102"
    assert data["amendment_version"] == 2
    assert data["forms_created"] >= 2
