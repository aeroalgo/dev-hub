"""Pydantic models for mb-scaffold."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ScaffoldRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    epic_id: str
    role: str = "back"
    phase: str  # plan, decompose, implement, qa, analyze, audit
    step_id: Optional[str] = None
    step_slug: Optional[str] = None
    from_plan: bool = False
    all_steps: bool = False
    force: bool = False
    dry_run: bool = False


class ScaffoldResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="mb-scaffold-result/v1", alias="schema")
    ok: bool = True
    created: List[str] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    dry_run: bool = False
    error: Optional[str] = None
