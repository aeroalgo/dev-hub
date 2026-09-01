"""loop-repair-result/v1 — typed gate-repair outcome."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_REPAIR_RESULT = "loop-repair-result/v1"

RepairStatus = Literal["done", "partial", "fail"]


class RepairResultRecord(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_REPAIR_RESULT)
    agent_id: str
    status: RepairStatus
    fixed_blockers: list[str] = Field(default_factory=list)
    remaining_blockers: list[str] = Field(default_factory=list)
    recorded_at: str

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_REPAIR_RESULT:
            raise ValueError(f"unsupported repair result schema: {value!r}")
        return value

    @field_validator("agent_id", mode="before")
    @classmethod
    def _strip_agent(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("status")
    @classmethod
    def _status_lower(cls, value: str) -> str:
        return value.lower()
