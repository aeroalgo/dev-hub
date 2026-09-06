"""loop-gate-verdict/v1 — typed gate verdict sidecar."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_GATE_VERDICT = "loop-gate-verdict/v1"

GateVerdictValue = Literal["PASS", "FAIL", "BLOCKED"]


class GateVerdictRecord(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_GATE_VERDICT)
    agent_id: str
    verdict: GateVerdictValue
    step_id: str
    session_id: str
    epic_id: str
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
    def _strip_required_string(cls, value: object) -> object:
        if value is None:
            raise ValueError("field is required and cannot be None")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("field cannot be empty or whitespace only")
            return stripped
        return value

    @field_validator("recorded_at")
    @classmethod
    def _validate_iso_recorded_at(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("recorded_at must be a non-empty ISO 8601 string")
        # Ensure it parses as a valid ISO 8601 datetime
        cleaned = value.strip().replace("Z", "+00:00")
        try:
            datetime.fromisoformat(cleaned)
        except Exception as exc:
            raise ValueError(f"recorded_at is not a valid ISO 8601 timestamp: {value!r}") from exc
        return value.strip()

    @field_validator("verdict")
    @classmethod
    def _verdict_upper(cls, value: str) -> str:
        return value.upper()
