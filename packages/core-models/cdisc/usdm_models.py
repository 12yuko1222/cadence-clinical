"""CDISC USDM v2.0 and v3.0 Pydantic v2 data models.

Provides strictly-typed objects representing the Unified Study Data Model (USDM)
protocol graph structure, including study designs, encounters, activities, and
eligibility criteria.

Requirements: PRD-SYS-001
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Code(BaseModel):
    """USDM Code / Concept representation."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    code: str
    code_system: str = Field(alias="codeSystem")
    code_system_version: Optional[str] = Field(default=None, alias="codeSystemVersion")
    decode: str


class SyntaxTemplate(BaseModel):
    """Syntax template definition for rules and eligibility criteria."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: Optional[str] = None
    text: str
    notes: List[str] = Field(default_factory=list)


class EligibilityCriterion(BaseModel):
    """Eligibility criterion (Inclusion or Exclusion)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    criterion_type: str = Field(
        alias="criterionType", description="Inclusion or Exclusion"
    )
    category: Optional[str] = None
    text: Optional[str] = None
    template: Optional[SyntaxTemplate] = None


class Activity(BaseModel):
    """Study activity or procedure definition."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    description: Optional[str] = None
    defined_procedures: List[Dict[str, Any]] = Field(
        default_factory=list, alias="definedProcedures"
    )


class Encounter(BaseModel):
    """Study encounter / visit definition."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    encounter_type: str = Field(default="Visit", alias="encounterType")
    start_date: Optional[str] = Field(default=None, alias="startDate")
    end_date: Optional[str] = Field(default=None, alias="endDate")


class StudyArm(BaseModel):
    """Study arm definition."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    arm_type: str = Field(default="Treatment", alias="armType")
    description: Optional[str] = None


class StudyEpoch(BaseModel):
    """Study epoch definition."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    epoch_type: str = Field(default="Screening", alias="epochType")
    sequence_number: int = Field(default=1, alias="sequenceNumber")


class StudyDesign(BaseModel):
    """Study design containing arms, epochs, encounters, activities, and criteria."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    design_type: Optional[str] = Field(default=None, alias="designType")
    arms: List[StudyArm] = Field(default_factory=list)
    epochs: List[StudyEpoch] = Field(default_factory=list)
    encounters: List[Encounter] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)
    eligibility_criteria: List[EligibilityCriterion] = Field(
        default_factory=list, alias="eligibilityCriteria"
    )


class USDMStudy(BaseModel):
    """Root USDM protocol study specification container."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    protocol_title: str = Field(alias="protocolTitle")
    usdm_version: str = Field(default="3.0", alias="usdmVersion")
    study_designs: List[StudyDesign] = Field(default_factory=list, alias="studyDesigns")
