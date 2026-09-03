"""Pydantic schema for epic-plan/v1 specifications."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Requirement(BaseModel):
    id: str
    text: str


class OutlineStep(BaseModel):
    step_id: str
    title: str
    maps_to: List[str] = Field(default_factory=list)


class StageSummary(BaseModel):
    title: str
    steps: List[str] = Field(default_factory=list)


class PlanSummary(BaseModel):
    step_count_floor: int
    requirement_count: int


class FormulaRef(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None


class SunsetRef(BaseModel):
    target: str
    action: Optional[str] = None


class TechnologyAxiom(BaseModel):
    axiom: Optional[str] = None


class PlanSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="epic-plan/v1", alias="schema")
    plan_id: str
    level: str
    title: Optional[str] = None
    formula: Optional[FormulaRef] = None
    summary: PlanSummary
    requirements: List[Requirement] = Field(default_factory=list)
    outline_steps: List[OutlineStep] = Field(default_factory=list)
    stages: List[StageSummary] = Field(default_factory=list)
    sunset_refs: List[SunsetRef] = Field(default_factory=list)
    technology_axiom: Optional[TechnologyAxiom] = None
