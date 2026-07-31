"""Unit test suite for Delegation of Authority (DOA) log Pydantic models.

Requirements: PRD-SYS-001
"""

from execution.doa_models import (
    DOAAssignmentRecord,
    DOATaskDelegationEnum,
    DOATaskRoleEnum,
)

import packages  # noqa: F401


def test_doa_assignment_record_creation() -> None:
    """Validate DOAAssignmentRecord model instantiation and field constraints.

    Requirements: PRD-SYS-001
    """
    record = DOAAssignmentRecord(
        record_id="doa_rec_001",
        study_id="study_doa_01",
        site_id="site_doa_101",
        personnel_name="Dr. Sarah Connor",
        personnel_email="sconnor@site.org",
        role=DOATaskRoleEnum.SUB_INVESTIGATOR,
        delegated_tasks=[
            DOATaskDelegationEnum.SUBJECT_INFORMED_CONSENT,
            DOATaskDelegationEnum.PHYSICAL_EXAMINATION,
            DOATaskDelegationEnum.AE_SAE_REPORTING,
        ],
        start_date="2026-07-01",
        is_active=True,
        signed_off=False,
    )

    assert record.record_id == "doa_rec_001"
    assert record.role == DOATaskRoleEnum.SUB_INVESTIGATOR
    assert len(record.delegated_tasks) == 3
    assert DOATaskDelegationEnum.SUBJECT_INFORMED_CONSENT in record.delegated_tasks
    assert record.signed_off is False
