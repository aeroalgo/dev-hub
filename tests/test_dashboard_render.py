"""Tests for loop.dashboard.render module."""

from __future__ import annotations

import json
from loop.dashboard.render import render_html, render_json
from loop.dashboard.schema import DashboardReport, EpisodeSummary, TaskRow
from loop.incidents.metrics import MetricsRecord
from loop.incidents.schema import IncidentRecord


def _make_report() -> DashboardReport:
    metrics = MetricsRecord(
        counters={"sessions_total": 10, "incidents_opened": 3},
        rates={"halt_rate": 0.20},
        updated_at="2026-09-01T12:00:00Z",
    )
    incident = IncidentRecord(
        incident_id="inc-001",
        status="open",
        opened_at="2026-09-01T10:00:00Z",
        project_root="/tmp/repo",
        epic_id="T-HUB-038",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="sess-001",
        source="test",
        diagnostic_codes=["TEST_ERR"],
        fingerprint="fp123",
    )
    episode = EpisodeSummary(
        episode_id="ep-001",
        started_at="2026-09-01T09:00:00Z",
        epic_id="T-HUB-038",
        role="back",
        armed_step="s01",
        decide="FINISH",
    )
    task = TaskRow(
        epic_id="T-HUB-038",
        role="back",
        phase="BACK IMPLEMENT",
        step="s02",
        title="Render HTML",
    )
    return DashboardReport(
        generated_at="2026-09-01T12:00:00Z",
        cwd="/tmp/repo",
        days_window=7,
        metrics=metrics,
        open_incidents=[incident],
        events_by_kind={"EPISODE_START": 10, "INCIDENT_OPEN": 3},
        last_episodes=[episode],
        epic_progress=[task],
    )


def test_html_structure() -> None:
    report = _make_report()
    html = render_html(report)
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html
    assert "Metrics" in html
    assert "Open Incidents" in html
    assert "Last Episodes" in html
    assert "Events by Kind" in html
    assert "Epic Progress" in html
    assert "20.00%" in html


def test_html_no_external_cdn() -> None:
    report = _make_report()
    html = render_html(report)
    assert "http://" not in html
    assert "https://" not in html
    assert "cdn" not in html.lower()


def test_json_schema_valid() -> None:
    report = _make_report()
    res = render_json(report)
    data = json.loads(res)
    assert data.get("schema") == "dashboard-report/v1"
    assert data["metrics"]["counters"]["sessions_total"] == 10
    assert len(data["open_incidents"]) == 1
