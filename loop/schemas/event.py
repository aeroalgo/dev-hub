"""LoopEvent Pydantic schema for events.jsonl records."""

from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

_EVENT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

EVENT_SCHEMA: Literal["loop-event/v2"] = "loop-event/v2"
EVENT_KINDS: frozenset[str] = frozenset({
    "audit_done",
    "qa_pass",
    "qa_fail",
    "bugfix_done",
    "reflection_done",
    "incident_opened",
    "incident_resolved",
    "repair_applied",
    "tier1_spawn",
    "tier1_verify_pass",
    "tier1_verify_fail",
    "tier1_escalated",
    "implement_done",
    "decompose_step_done",
    "phase_transition",
    "traceability_warn",
    "traceability_fail",
})


class LoopEvent(BaseModel):
    """Pydantic model representing a canonical loop event record (loop-event/v2)."""

    model_config = {"extra": "forbid"}

    schema_version: Literal["loop-event/v2"] = Field(default="loop-event/v2", alias="schema")
    event_id: str
    seq: int = Field(gt=0)
    kind: str
    artifact: str
    artifact_sha256: str
    epic_id: str
    epoch: int = Field(ge=0, default=0)
    t: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        if not _EVENT_ID_RE.fullmatch(v):
            raise ValueError("event_id has an invalid type or format")
        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if v not in EVENT_KINDS:
            raise ValueError(f"kind must be one of {sorted(EVENT_KINDS)}")
        return v

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_sha256(cls, v: str) -> str:
        if not _SHA256_RE.fullmatch(v):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256")
        return v

    @field_validator("epic_id")
    @classmethod
    def validate_epic_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("epic_id must be a non-empty string")
        return v

    @field_validator("t")
    @classmethod
    def validate_t(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("t must be a non-empty timestamp string")
        return v
