"""loop-incident/v1 — schema for orchestration incidents."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_INCIDENT = "loop-incident/v1"

IncidentStatus = Literal["open", "resolved", "escalated"]


def compute_incident_id(
    project_root: str,
    epic_id: str,
    step_id: str,
    session_id: str,
    diagnostic_codes: list[str],
    fingerprint: str,
) -> str:
    """Compute deterministic SHA256 incident_id from canonical subset of fields."""
    canonical_payload = {
        "project_root": project_root.strip(),
        "epic_id": epic_id.strip(),
        "step_id": step_id.strip(),
        "session_id": session_id.strip(),
        "diagnostic_codes": sorted(code.strip() for code in diagnostic_codes),
        "fingerprint": fingerprint.strip(),
    }
    dumped = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class IncidentRecord(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_INCIDENT)
    incident_id: str
    status: IncidentStatus = "open"
    opened_at: str
    resolved_at: str | None = None
    project_root: str
    epic_id: str
    step_id: str
    phase: str
    session_id: str
    source: str
    diagnostic_codes: list[str] = Field(default_factory=list)
    fingerprint: str
    tier0_attempts: int = 0
    tier0_repair_log: list[dict[str, Any]] = Field(default_factory=list)
    resolution_tier: str | None = None
    resolution_action: str | None = None
    runbook_rel: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if value != SCHEMA_LOOP_INCIDENT:
            raise ValueError(f"unsupported incident schema version: {value!r}")
        return value
