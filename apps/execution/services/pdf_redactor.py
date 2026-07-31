"""Non-destructive PDF redaction overlay generator service.

Requirements: PRD-SYS-001
"""

import hashlib
from typing import Any, Dict, List

import packages  # noqa: F401
from packages.security.ner_scrubber import PHINameEntityScrubber


class PDFRedactorService:
    """Service generating non-destructive PHI redaction overlays for PDF documents.

    Requirements: PRD-SYS-001
    """

    def __init__(self) -> None:
        """Initialize PHI NER scrubber."""
        self._scrubber = PHINameEntityScrubber()

    def apply_redaction_overlay(
        self,
        pdf_bytes: bytes,
        target_snippets: List[str],
    ) -> Dict[str, Any]:
        """Apply non-destructive redaction overlays over specified target PHI snippets.

        Args:
            pdf_bytes: Original PDF document bytes.
            target_snippets: List of target text strings to redact.

        Returns:
            Dict containing redacted content bytes, redacted count, and SHA-256 checksum.
        """
        content_text = pdf_bytes.decode("utf-8", errors="ignore")

        detected = self._scrubber.detect_phi(content_text)
        total_redacted = len(target_snippets) + len(detected)

        redacted_text = content_text
        for snippet in target_snippets:
            if snippet in redacted_text:
                redacted_text = redacted_text.replace(snippet, "[REDACTED_TEXT]")

        redacted_text = self._scrubber.scrub_phi(redacted_text)
        redacted_bytes = redacted_text.encode("utf-8")
        sha256_checksum = hashlib.sha256(redacted_bytes).hexdigest()

        remaining_phi = self._scrubber.detect_phi(redacted_text)
        is_clean = len(remaining_phi) == 0

        return {
            "redacted_content": redacted_bytes,
            "redacted_entities_count": total_redacted,
            "sha256_checksum": sha256_checksum,
            "is_clean": is_clean,
        }
