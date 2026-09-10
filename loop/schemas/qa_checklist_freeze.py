"""loop-qa-checklist-freeze/v1 — frozen AC matrix for QA anti-ratchet."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_QA_CHECKLIST_FREEZE = "loop-qa-checklist-freeze/v1"

EligibleBlockerClass = Literal[
    "suite_red",
    "ac_gap",
    "leftover",
    "orphan_ref",
    "prior_open",
    "behavior_smoke",
]

ELIGIBLE_BLOCKER_CLASSES: frozenset[str] = frozenset(
    {
        "suite_red",
        "ac_gap",
        "leftover",
        "orphan_ref",
        "prior_open",
        "behavior_smoke",
    }
)

REQA_CYCLE_MAX = 3


class QaChecklistFreeze(BaseModel):
    """Frozen verify-qa matrix for one epic QA window (first QA → re-QA)."""

    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_QA_CHECKLIST_FREEZE)
    epic_id: str
    ac_plus: list[str] = Field(default_factory=list)
    ac_minus: list[str] = Field(default_factory=list)
    section_011: list[str] = Field(default_factory=list)
    prior_blockers: list[str] = Field(default_factory=list)
    source: Literal["plan_ac", "qa_consumes", "qa_artifact", "hybrid"] = "plan_ac"
    source_path: str = ""
    checklist_sha256: str = ""
    frozen_at: str = ""
    verify_scope: Literal["full", "prior_only"] = "full"
    reqa_cycles: int = 0

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_QA_CHECKLIST_FREEZE:
            raise ValueError(f"unsupported qa checklist freeze schema: {value!r}")
        return value
