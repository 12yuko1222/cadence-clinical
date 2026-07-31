"""Unit test suite for PHI Named Entity Recognition (NER) scrubber.

Requirements: PRD-SYS-001
"""

import packages  # noqa: F401
from packages.security.ner_scrubber import PHINameEntityScrubber


def test_detect_phi_patterns() -> None:
    """Validate detect_phi identifies SSN, email, phone number, and MRN tokens.

    Requirements: PRD-SYS-001
    """
    scrubber = PHINameEntityScrubber()
    sample_text = (
        "Patient John Doe (MRN:#12345678) DOB:1980-05-12. "
        "Contact: john.doe@example.com or 555-123-4567. "
        "SSN: 000-12-3456."
    )

    entities = scrubber.detect_phi(sample_text)
    assert len(entities) >= 4

    types = [e["entity_type"] for e in entities]
    assert "SSN" in types
    assert "EMAIL" in types
    assert "PHONE" in types
    assert "MRN" in types
    assert "DOB" in types


def test_scrub_phi_redaction() -> None:
    """Validate scrub_phi replaces PHI tokens with redaction tags.

    Requirements: PRD-SYS-001
    """
    scrubber = PHINameEntityScrubber()
    sample_text = "Patient SSN is 123-45-6789 and email is patient@hospital.org"

    scrubbed = scrubber.scrub_phi(sample_text)

    assert "123-45-6789" not in scrubbed
    assert "patient@hospital.org" not in scrubbed
    assert "[REDACTED_SSN]" in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
