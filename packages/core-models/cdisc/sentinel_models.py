"""Pydantic data models for Protocol Quality Sentinel and site feasibility analyzer.

Requirements: PRD-SYS-001
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class QualityRuleFinding(BaseModel):
    """Specific protocol quality rule finding.

    Requirements: PRD-SYS-001
    """

    rule_id: str = Field(
        ..., description="Unique quality rule ID (e.g. SENTINEL_REQ_01)"
    )
    severity: str = Field(..., description="Severity level: ERROR, WARNING, INFO")
    category: str = Field(..., description="Category: Structural, Regulatory, Burden")
    message: str = Field(..., description="Human-readable rule finding message")
    target_node_id: Optional[str] = Field(None, description="Target USDM graph node ID")


class ProtocolQualityScore(BaseModel):
    """Protocol Quality Sentinel evaluation summary report.

    Requirements: PRD-SYS-001
    """

    study_id: str = Field(..., description="Target protocol study ID")
    quality_score: float = Field(
        ..., description="Overall protocol quality score (0.0 to 100.0)"
    )
    patient_burden_index: float = Field(
        ..., description="Calculated patient operational burden score"
    )
    findings: List[QualityRuleFinding] = Field(
        default_factory=list, description="Quality findings"
    )
    passed: bool = Field(..., description="True if no ERROR severity findings exist")
