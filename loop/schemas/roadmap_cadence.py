"""Typed roadmap-cadence/v1 contract — cadence state SoT schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_ROADMAP_CADENCE = "roadmap-cadence/v1"
CADENCE_PHASES = ("idle", "replan", "refactor", "resync")
CadencePhase = Literal["idle", "replan", "refactor", "resync"]
ReplanOutcome = Literal["complete", "skip"]


class ReplanGap(BaseModel):
    """Structured representation of a single gap item."""

    gap_id: str | None = None
    description: str = ""
    severity: str = "critical"

    model_config = {"populate_by_name": True, "extra": "allow"}


class ReplanEvidence(BaseModel):
    """Structured evidence for a replan outcome."""

    critical_gaps: list[Any] = Field(default_factory=list)
    cosmetic_gaps: list[Any] = Field(default_factory=list)
    gaps: list[Any] = Field(default_factory=list)
    reason: str | None = None
    notes: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}

    def has_critical_gaps(self) -> bool:
        """Return True if evidence contains any critical gap."""
        if self.critical_gaps:
            return True
        for g in self.gaps:
            if isinstance(g, dict):
                sev = str(g.get("severity", "")).lower()
                if sev in ("critical", "high", "blocker"):
                    return True
                if sev in ("cosmetic", "low", "minor", "trivial") or g.get("cosmetic") is True:
                    continue
                desc = str(g.get("description", g.get("text", g.get("gap", "")))).lower()
                if "cosmetic" not in desc and "trivial" not in desc:
                    return True
            elif isinstance(g, ReplanGap):
                if g.severity.lower() in ("critical", "high", "blocker"):
                    return True
                if g.severity.lower() not in ("cosmetic", "low", "minor", "trivial") and "cosmetic" not in g.description.lower():
                    return True
            elif isinstance(g, str):
                gl = g.lower()
                if "cosmetic" not in gl and "trivial" not in gl:
                    return True
        return False


class ResyncEvidence(BaseModel):
    """Structured evidence for cadence resync phase."""

    high_count: int = 0
    resync_action: str = ""
    stale_epics: list[str] = Field(default_factory=list)
    timestamp: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}


class ReplanSkipRecord(BaseModel):
    """Record of a skipped replan item with mandatory evidence or reason."""

    epic_id: str
    outcome: Literal["skip"] = "skip"
    reason: str = ""
    evidence: ReplanEvidence | dict[str, Any] | None = None
    timestamp: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class ReplanOutcomeRecord(BaseModel):
    """Outcome record for an epic in replan phase."""

    epic_id: str
    outcome: ReplanOutcome
    reason: str = ""
    evidence: ReplanEvidence | dict[str, Any] | None = None
    timestamp: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class RoadmapCadenceState(BaseModel):
    """Roadmap cadence state machine representation."""

    schema_version: str = Field(alias="schema", default=SCHEMA_ROADMAP_CADENCE)
    phase: CadencePhase = "idle"
    counter: int = Field(default=0, ge=0)
    every_n: int = Field(default=4, ge=1)
    review_window_n: int = Field(default=8, ge=1)
    pair_ids: list[str] = Field(default_factory=list)
    feature_history: list[str] = Field(default_factory=list)
    replan_epic_id: str | None = None
    replan_started: bool = False
    replan_outcomes: dict[str, ReplanOutcomeRecord] = Field(default_factory=dict)
    resync_evidence: ResyncEvidence | dict[str, Any] | None = None
    resync_summary: dict[str, Any] | None = None

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != SCHEMA_ROADMAP_CADENCE:
            raise ValueError(f"unsupported roadmap cadence schema: {value!r}")
        return value

    @field_validator("pair_ids", mode="before")
    @classmethod
    def _validate_pair_ids(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("pair_ids must be a list")
        return [str(v).strip() for v in value if str(v).strip()]

    @field_validator("feature_history", mode="before")
    @classmethod
    def _validate_feature_history(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("feature_history must be a list")
        return [str(v).strip() for v in value if str(v).strip()]


__all__ = [
    "CADENCE_PHASES",
    "SCHEMA_ROADMAP_CADENCE",
    "CadencePhase",
    "ReplanEvidence",
    "ReplanGap",
    "ReplanOutcome",
    "ReplanOutcomeRecord",
    "ReplanSkipRecord",
    "ResyncEvidence",
    "RoadmapCadenceState",
]
