"""Unit test suite for PDF redaction overlay generator.

Requirements: PRD-SYS-001
"""

import packages  # noqa: F401
from apps.execution.services.pdf_redactor import PDFRedactorService


def test_pdf_redaction_overlay_generation() -> None:
    """Validate PDFRedactorService applies non-destructive redactions and verifies output cleanliness.

    Requirements: PRD-SYS-001
    """
    redactor = PDFRedactorService()
    pdf_sample = (
        b"Subject Name: Jane Doe. SSN: 111-22-3333. Clinical Assessment Report."
    )

    result = redactor.apply_redaction_overlay(pdf_sample, ["Jane Doe"])

    assert result["is_clean"] is True
    assert result["redacted_entities_count"] >= 2
    assert b"111-22-3333" not in result["redacted_content"]
    assert b"Jane Doe" not in result["redacted_content"]
    assert len(result["sha256_checksum"]) == 64
