"""Deterministic Protocol Quality Sentinel and site feasibility analyzer service.

Requirements: PRD-SYS-001
"""

from typing import Any, Dict

from cdisc.sentinel_models import ProtocolQualityScore, QualityRuleFinding

import packages  # noqa: F401


class ProtocolQualitySentinel:
    """Quality evaluation service auditing USDM study specifications against regulatory rules.

    Requirements: PRD-SYS-001
    """

    def evaluate_protocol_quality(
        self, study_payload: Dict[str, Any]
    ) -> ProtocolQualityScore:
        """Audit authored protocol payload and compute quality score and burden index.

        Args:
            study_payload: USDM Study dictionary structure.

        Returns:
            ProtocolQualityScore summary report.
        """
        study_id = str(study_payload.get("id", "study_unnamed"))
        findings: list[QualityRuleFinding] = []

        # Rule 1: Check Study Design presence
        designs = (
            study_payload.get("studyDesigns")
            or study_payload.get("study_designs")
            or []
        )
        if not designs:
            findings.append(
                QualityRuleFinding(
                    rule_id="SENTINEL_STRUCT_01",
                    severity="ERROR",
                    category="Structural",
                    message="Protocol is missing required study design structure.",
                    target_node_id=study_id,
                )
            )

        # Rule 2: Check Eligibility Criteria
        criteria = (
            study_payload.get("eligibilityCriteria")
            or study_payload.get("eligibility_criteria")
            or []
        )
        if not criteria:
            findings.append(
                QualityRuleFinding(
                    rule_id="SENTINEL_REG_02",
                    severity="WARNING",
                    category="Regulatory",
                    message="Protocol lacks defined inclusion and exclusion criteria.",
                    target_node_id=study_id,
                )
            )

        # Rule 3: Check Objectives / Endpoints
        objectives = study_payload.get("objectives") or []
        if not objectives and designs:
            first_design = designs[0] if isinstance(designs, list) else {}
            objectives = (
                first_design.get("objectives") if isinstance(first_design, dict) else []
            )

        if not objectives:
            findings.append(
                QualityRuleFinding(
                    rule_id="SENTINEL_REG_03",
                    severity="ERROR",
                    category="Regulatory",
                    message="Protocol lacks defined primary study objectives or endpoints.",
                    target_node_id=study_id,
                )
            )

        # Calculate Burden Index
        encounter_count = 0
        activity_count = 0

        if designs and isinstance(designs, list):
            for d in designs:
                if isinstance(d, dict):
                    encounter_count += len(d.get("encounters", []))
                    activity_count += len(d.get("activities", []))

        burden_index = float(encounter_count * 1.5 + activity_count * 2.0)

        if burden_index > 25.0:
            findings.append(
                QualityRuleFinding(
                    rule_id="SENTINEL_BURDEN_04",
                    severity="WARNING",
                    category="Burden",
                    message=f"Patient Operational Burden Index ({burden_index:.1f}) exceeds recommended threshold (25.0).",
                    target_node_id=study_id,
                )
            )

        # Calculate Overall Quality Score
        error_count = len([f for f in findings if f.severity == "ERROR"])
        warning_count = len([f for f in findings if f.severity == "WARNING"])

        base_score = 100.0 - (25.0 * error_count + 10.0 * warning_count)
        quality_score = max(0.0, min(100.0, base_score))

        return ProtocolQualityScore(
            study_id=study_id,
            quality_score=quality_score,
            patient_burden_index=burden_index,
            findings=findings,
            passed=error_count == 0,
        )
