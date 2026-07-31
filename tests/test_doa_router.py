"""Integration test suite for Delegation of Authority (DOA) log REST API endpoints.

Requirements: PRD-SYS-001
"""

import os
import time

from fastapi.testclient import TestClient
from jose import jwt

import packages  # noqa: F401
from apps.execution.main import app
from packages.security.signing import generate_gateway_signature

client = TestClient(app)
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "internal-gateway-secret-12345").encode(
    "utf-8"
)


def _make_doa_auth_headers(
    user_id: str = "pi_user_301",
    roles: str = "principal_investigator",
    change_reason: str = "Approve DOA Assignment",
    action: str = "/api/v1/execution/doa/sign-off",
) -> dict:
    timestamp = str(time.time())
    signature = generate_gateway_signature(
        user_id=user_id,
        roles=roles,
        timestamp=timestamp,
        secret=GATEWAY_SECRET,
        change_reason=change_reason,
        tenant_id="tenant_default",
    )
    headers = {
        "X-User-Id": user_id,
        "X-User-Roles": roles,
        "X-Gateway-Timestamp": timestamp,
        "X-Gateway-Signature": signature,
        "X-Signature-Version": "2",
        "X-Change-Reason": change_reason,
        "X-Tenant-Id": "tenant_default",
    }

    sig_payload = {
        "sub": user_id,
        "username": user_id,
        "action": action,
        "semantic_action": "execution.form.signoff",
        "roles": [roles],
        "iat": time.time(),
        "exp": time.time() + 300.0,
        "jti": f"jti_{time.time()}_{user_id}",
    }

    sig_token = jwt.encode(sig_payload, GATEWAY_SECRET, algorithm="HS256")
    headers["X-Sig-Token"] = sig_token
    return headers


def test_doa_assignment_and_signoff_api_flow() -> None:
    """Validate POST assignment, POST sign-off, and GET site DOA log API endpoints.

    Requirements: PRD-SYS-001
    """
    headers = _make_doa_auth_headers(
        user_id="pi_user_301",
        roles="principal_investigator",
        change_reason="Approve DOA Assignment",
    )

    study_id = "study_doa_api_01"
    site_id = "site_doa_301"

    # Step 1: Add DOA Assignment
    res_assign = client.post(
        "/api/v1/execution/doa/assignment",
        json={
            "study_id": study_id,
            "site_id": site_id,
            "personnel_name": "Nurse Jacqueline Thorne",
            "personnel_email": "jthorne@site.org",
            "role": "STUDY_NURSE",
            "delegated_tasks": ["PHYSICAL_EXAMINATION", "CRF_DATA_ENTRY"],
            "start_date": "2026-07-20",
        },
        headers=headers,
    )

    assert res_assign.status_code == 201
    data_assign = res_assign.json()
    rec_id = data_assign["record_id"]
    assert data_assign["signed_off"] is False

    # Step 2: PI Sign-Off
    res_sign = client.post(
        "/api/v1/execution/doa/sign-off",
        json={
            "record_id": rec_id,
            "reason_for_change": "PI Delegation Endorsement",
        },
        headers=headers,
    )

    assert res_sign.status_code == 200
    data_sign = res_sign.json()
    assert data_sign["signed_off"] is True

    # Step 3: Get Site DOA Log
    res_log = client.get(
        f"/api/v1/execution/doa/log/{study_id}/{site_id}",
        headers=headers,
    )

    assert res_log.status_code == 200
    log_entries = res_log.json()
    assert len(log_entries) >= 1
    assert log_entries[0]["personnel_name"] == "Nurse Jacqueline Thorne"
