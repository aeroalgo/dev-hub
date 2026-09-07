"""loop/schemas/telemetry.py — Typed telemetry schemas for context ledger enforcement.

Defines ActorTelemetry, TelemetryAggregate, and FinishReceipt models.
Ensures zero content leakage, machine-readable counters, actor/provider attribution,
and explicit non-green diagnostics on corruption or persistence failure.

Part of T-HUB-078 (FR-005, FR-007, FR-008, FR-010).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_CONTEXT_TELEMETRY = "context-telemetry/v1"
SCHEMA_FINISH_RECEIPT = "context-finish-receipt/v1"

# Prohibited keys that might indicate source code or secret payload leakage
FORBIDDEN_CONTENT_KEYS = frozenset(
    {
        "file_content",
        "content",
        "source_code",
        "body",
        "secret",
        "password",
        "token",
        "raw_lines",
    }
)


class ActorTelemetry(BaseModel):
    """Metadata counters attributed to an individual session actor (root or subagent)."""

    actor_kind: Literal["root", "subagent"] = "root"
    agent_invocation_id: str
    runtime_provider: str = "claude"  # "claude" | "codex"
    parent_invocation_id: str | None = None
    unique_reads: int = 0
    duplicate_reads: int = 0
    bytes_read: int = 0
    ranges_read: int = 0
    monolith_plan_attempts: int = 0
    search_exceptions: int = 0
    denials: int = 0
    invalidations: int = 0
    total_requests: int = 0
    highest_repeat_path: str | None = None
    files_tracked: int = 0

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("agent_invocation_id", "runtime_provider", mode="before")
    @classmethod
    def _validate_non_empty_str(cls, val: Any) -> str:
        if not val or not str(val).strip():
            return "root"
        return str(val).strip()


class ProviderTelemetry(BaseModel):
    """Aggregated counters for a runtime provider (e.g. claude vs codex)."""

    runtime_provider: str
    unique_reads: int = 0
    duplicate_reads: int = 0
    bytes_read: int = 0
    ranges_read: int = 0
    monolith_plan_attempts: int = 0
    search_exceptions: int = 0
    total_requests: int = 0

    model_config = {"populate_by_name": True, "extra": "forbid"}


class TelemetryAggregate(BaseModel):
    """Session-wide aggregated context telemetry across all actors and providers."""

    schema_version: str = Field(alias="schema", default=SCHEMA_CONTEXT_TELEMETRY)
    session_id: str
    project_root: str
    unique_reads: int = 0
    duplicate_reads: int = 0
    bytes_read: int = 0
    ranges_read: int = 0
    monolith_plan_attempts: int = 0
    search_exceptions: int = 0
    highest_repeat_path: str | None = None
    total_requests: int = 0
    denials: int = 0
    invalidations: int = 0
    files_tracked: int = 0
    actors: list[ActorTelemetry] = Field(default_factory=list)
    provider_breakdown: dict[str, dict[str, int]] = Field(default_factory=dict)
    is_green: bool = True
    diagnostic_code: str | None = None

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _validate_schema(cls, val: str) -> str:
        if val != SCHEMA_CONTEXT_TELEMETRY:
            raise ValueError(f"unsupported context telemetry schema: {val!r}")
        return val


class FinishReceipt(BaseModel):
    """Final machine-readable receipt generated at session completion or handoff."""

    schema_version: str = Field(alias="schema", default=SCHEMA_FINISH_RECEIPT)
    session_id: str
    epic_id: str | None = None
    step_id: str | None = None
    aggregate: TelemetryAggregate
    status: Literal["green", "non_green", "corrupt", "missing"] = "green"
    diagnostics: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    secret_free: bool = True

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _validate_schema(cls, val: str) -> str:
        if val != SCHEMA_FINISH_RECEIPT:
            raise ValueError(f"unsupported finish receipt schema: {val!r}")
        return val
