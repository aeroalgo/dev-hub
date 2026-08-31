"""Pydantic schema for loop checkpoint persistence (loop-checkpoint/v1)."""

from __future__ import annotations

import warnings
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

warnings.filterwarnings("ignore", message=".*shadows an attribute in parent.*")

CHECKPOINT_SCHEMA = "loop-checkpoint/v1"

CHECKPOINT_STAGES = frozenset(
    {
        "prepared",
        "dispatched",
        "interrupted",
        "evidence_recorded",
        "handoff_validated",
        "blocked",
        "committed",
    }
)

CHECKPOINT_STATUSES = frozenset({"active", "interrupted", "need_human", "committed"})

CHECKPOINT_ACTIONS = frozenset({"invoke", "resume", "reconcile", "halt", "advance", "none"})

CHECKPOINT_RESUME_POLICIES = frozenset({"same_step", "manual", "next_step", "halt"})


class CheckpointRecord(BaseModel):
    """Schema for checkpoint persistence record in runner/epic execution."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    schema: Literal["loop-checkpoint/v1"] = "loop-checkpoint/v1"
    checkpoint_seq: int = Field(ge=1)
    checkpoint_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    runner_id: str | None = None
    identity: dict[str, str] = Field(default_factory=dict)
    step_id: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    phase_epoch: int | str = Field(min_length=1)
    projection_hash: str | None = None
    stage: str
    status: str
    next_action: str
    resume_policy: str
    context_fingerprint: str | None = None
    index_fingerprint: str | None = None
    retry_count: int = Field(default=0, ge=0)
    degraded_count: int = Field(default=0, ge=0)
    session_boundary: bool | None = None
    reason: str | None = None
    metadata: dict[str, Any] | None = Field(default_factory=dict)
    updated_at: str | None = None

    @field_validator("metadata", mode="before")
    @classmethod
    def _coerce_metadata(cls, v: Any) -> dict[str, Any]:
        if not isinstance(v, dict):
            return {}
        return v

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, v: str) -> str:
        if v not in CHECKPOINT_STAGES:
            raise ValueError(f"invalid stage: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in CHECKPOINT_STATUSES:
            raise ValueError(f"invalid status: {v}")
        return v

    @field_validator("next_action")
    @classmethod
    def _validate_next_action(cls, v: str) -> str:
        if v not in CHECKPOINT_ACTIONS:
            raise ValueError(f"invalid next_action: {v}")
        return v

    @field_validator("resume_policy")
    @classmethod
    def _validate_resume_policy(cls, v: str) -> str:
        if v not in CHECKPOINT_RESUME_POLICIES:
            raise ValueError(f"invalid resume_policy: {v}")
        return v

    @field_validator("phase_epoch", mode="before")
    @classmethod
    def _coerce_epoch(cls, v: Any) -> str:
        if v is None:
            raise ValueError("checkpoint_epoch_invalid")
        return str(v).strip()
