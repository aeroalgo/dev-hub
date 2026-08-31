"""loop-handoff/v1 — machine-readable activeContext frontmatter."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_HANDOFF = "loop-handoff/v1"

LoopHandoffRole = Literal["BACK", "FRONT", "INTEG"]


class LoopHandoffFrontmatter(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_HANDOFF)
    role: LoopHandoffRole
    mode: str
    epic_id: str
    step_id: str | None = None
    reason_code: str | None = None
    projection_hash: str | None = None

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_HANDOFF:
            raise ValueError(f"unsupported handoff schema: {value!r}")
        return value

    @field_validator("role", "mode", "epic_id", "step_id", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("role", mode="before")
    @classmethod
    def _role_upper(cls, value: object) -> object:
        if isinstance(value, str):
            upper = value.upper()
            if upper == "INTEGRATION":
                return "INTEG"
            return upper
        return value

    @field_validator("mode")
    @classmethod
    def _mode_upper(cls, value: str) -> str:
        return value.upper()

    def model_dump_frontmatter(self) -> dict[str, str | None]:
        data = {
            "schema": self.schema_version,
            "role": self.role,
            "mode": self.mode,
            "epic_id": self.epic_id,
        }
        if self.step_id:
            data["step_id"] = self.step_id
        if self.reason_code:
            data["reason_code"] = self.reason_code
        if self.projection_hash:
            data["projection_hash"] = self.projection_hash
        return data
