"""loop-repair-result/v1 — typed gate-repair outcome."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_LOOP_REPAIR_RESULT = "loop-repair-result/v1"

RepairStatus = Literal["done", "partial", "fail"]


class RepairResultRecord(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_REPAIR_RESULT)
    parent_evidence_id: str
    agent_id: str
    status: RepairStatus
    fixed_blockers: list[str] = Field(default_factory=list)
    remaining_blockers: list[str] = Field(default_factory=list)
    diagnostic: str | None = None
    recorded_at: str

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_REPAIR_RESULT:
            raise ValueError(f"unsupported repair result schema: {value!r}")
        return value

    @field_validator("parent_evidence_id", mode="before")
    @classmethod
    def _strip_parent_evidence(cls, value: object) -> object:
        if isinstance(value, str):
            val = value.strip()
            if not val:
                raise ValueError("parent_evidence_id cannot be empty")
            return val
        return value

    @field_validator("agent_id", mode="before")
    @classmethod
    def _validate_agent_id(cls, value: object) -> object:
        if isinstance(value, str):
            val = value.strip()
            if val != "gate-repair":
                raise ValueError(f"agent_id must be 'gate-repair', got {val!r}")
            return val
        raise ValueError(f"agent_id must be 'gate-repair', got {value!r}")

    @field_validator("status")
    @classmethod
    def _status_lower(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def _validate_repair_invariants(self) -> RepairResultRecord:
        fixed_set = set(self.fixed_blockers)
        remaining_set = set(self.remaining_blockers)
        intersection = fixed_set & remaining_set
        if intersection:
            raise ValueError(
                f"fixed_blockers and remaining_blockers must be disjoint; overlap: {sorted(intersection)}"
            )

        if self.status == "done":
            if self.remaining_blockers:
                raise ValueError(
                    f"status 'done' requires empty remaining_blockers; got {self.remaining_blockers}"
                )

        if self.status == "fail":
            if not self.remaining_blockers and not self.diagnostic:
                raise ValueError(
                    "status 'fail' requires non-empty remaining_blockers or diagnostic"
                )

        return self

