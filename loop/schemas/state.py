"""Pydantic schemas for epic state and drift counters."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class DriftCounters(BaseModel):
    """Drift and fallback counters tracking legacy repair executions."""

    handoff_projected: int = 0
    index_mirror_repair: int = 0
    fingerprint_stall_repair: int = 0
    gate_verdict_regex_fallback: int = 0
    schema_invalid: int = 0


class EpicState(BaseModel):
    """Runtime state schema for epic persistence (loop-state/v2)."""

    model_config = {"extra": "allow"}

    schema_version: Literal["loop-state/v2"] = "loop-state/v2"

    active: bool = False
    status: str = "idle"
    started_at: str | None = None
    updated_at: str | None = None
    halt_reason: str | None = None
    model: str | None = None
    last_verify_verdict: str | None = None
    last_verify_at: str | None = None
    pending_fingerprint_before: str | None = None
    load_now_before: str | list[str] | None = None

    drift_counters: DriftCounters = Field(default_factory=DriftCounters)
