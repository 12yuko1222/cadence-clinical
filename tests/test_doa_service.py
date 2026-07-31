"""Unit test suite for Delegation of Authority (DOA) log service and PI sign-off.

Requirements: PRD-SYS-001
"""

from execution.doa_models import DOATaskDelegationEnum, DOATaskRoleEnum

import packages  # noqa: F401
from apps.execution.services.doa_service import DOAService


def test_doa_service_assignment_and_pi_signoff() -> None:
    """Validate adding assignment to DOA log and signing off with PI eSignature.

    Requirements: PRD-SYS-001
    """
    service = DOAService()

    rec = service.add_assignment(
        study_id="study_doa_02",
        site_id="site_doa_202",
        personnel_name="Dr. Alex Rivera",
        personnel_email="arivera@site.org",
        role=DOATaskRoleEnum.SUB_INVESTIGATOR,
        delegated_tasks=[DOATaskDelegationEnum.CRF_DATA_ENTRY],
        start_date="2026-07-15",
    )

    assert rec.signed_off is False

    # Perform PI Sign-Off
    updated_rec = service.sign_off_assignment(
        record_id=rec.record_id,
        pi_user_id="pi_user_99",
        reason_for_change="PI Delegation Approval",
    )

    assert updated_rec.signed_off is True
