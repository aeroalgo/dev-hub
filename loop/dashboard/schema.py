"""Pydantic schemas for loop dashboard reports (dashboard-report/v1)."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from loop.incidents.metrics import MetricsRecord
from loop.incidents.schema import IncidentRecord

SCHEMA_DASHBOARD_REPORT = "dashboard-report/v1"


class EpisodeSummary(BaseModel):
    """Summary of a loop episode package."""

    episode_id: str
    started_at: str
    ended_at: str | None = None
    epic_id: str
    role: str
    armed_step: str
    decide: str | None = None
    halt_reason: str | None = None
    incident_count: int = 0


class TaskRow(BaseModel):
    """Active epic row parsed from memory-bank/tasks.md."""

    epic_id: str
    role: str
    phase: str
    step: str
    title: str = ""


class DashboardReport(BaseModel):
    """Aggregated dashboard metrics & incidents report (dashboard-report/v1)."""

    schema_version: str = Field(alias="schema", default=SCHEMA_DASHBOARD_REPORT)
    generated_at: str
    cwd: str
    days_window: int = 7
    metrics: MetricsRecord
    open_incidents: list[IncidentRecord] = Field(default_factory=list)
    events_by_kind: dict[str, int] = Field(default_factory=dict)
    last_episodes: list[EpisodeSummary] = Field(default_factory=list)
    epic_progress: list[TaskRow] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
