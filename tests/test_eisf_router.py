"""Integration test suite for eISF regulatory binder browsing and document upload REST API.

Requirements: PRD-SYS-001
"""

import base64

from fastapi.testclient import TestClient

import packages  # noqa: F401
from apps.execution.main import app
from tests.test_lock_router import _make_auth_headers

client = TestClient(app)


def test_upload_eisf_document_post_endpoint() -> None:
    """Validate POST /api/v1/execution/eisf/upload uploads regulatory binder document.

    Requirements: PRD-SYS-001
    """
    headers = _make_auth_headers(
        user_id="crc_user_101",
        roles="site_coordinator",
        change_reason="Upload Financial Disclosure Form",
    )

    content_bytes = b"Financial Disclosure Form Content 2026"
    content_b64 = base64.b64encode(content_bytes).decode("utf-8")

    response = client.post(
        "/api/v1/execution/eisf/upload",
        json={
            "study_id": "study_eisf_api_01",
            "site_id": "site_201",
            "category": "6_FINANCIAL_DISCLOSURE",
            "title": "Investigator Financial Disclosure",
            "file_name": "Financial_Disclosure.pdf",
            "content_base64": content_b64,
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["study_id"] == "study_eisf_api_01"
    assert data["site_id"] == "site_201"
    assert data["category"] == "6_FINANCIAL_DISCLOSURE"
    assert "sha256_hash" in data


def test_get_site_regulatory_binder_endpoint() -> None:
    """Validate GET /api/v1/execution/eisf/binder/{study_id}/{site_id} returns site documents.

    Requirements: PRD-SYS-001
    """
    headers = _make_auth_headers()

    response = client.get(
        "/api/v1/execution/eisf/binder/study_eisf_api_01/site_201",
        headers=headers,
    )

    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) >= 1
    assert docs[0]["site_id"] == "site_201"
