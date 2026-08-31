"""loop-gate-verdict/v1 — typed gate verdict sidecar."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_GATE_VERDICT = "loop-gate-verdict/v1"

GateVerdictValue = Literal["PASS", "FAIL", "BLOCKED"]


class GateVerdictRecord(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_GATE_VERDICT)
    agent_id: str
    verdict: GateVerdictValue
    step_id: str | None = None
    session_id: str | None = None
    epic_id: str | None = None
    recorded_at: str
    evidence_sha256: str | None = None

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_GATE_VERDICT:
            raise ValueError(f"unsupported gate verdict schema: {value!r}")
        return value

    @field_validator("agent_id", "step_id", "session_id", "epic_id", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("verdict")
    @classmethod
    def _verdict_upper(cls, value: str) -> str:
        return value.upper()
