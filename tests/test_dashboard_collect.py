"""Tests for loop.dashboard.collect module."""

from __future__ import annotations

import json
from pathlib import Path
from loop.dashboard.collect import collect
from loop.dashboard.schema import DashboardReport
from loop.incidents.metrics import compute_rates


def _setup_fixture_dir(tmp_path: Path) -> Path:
    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True)

    # 1. metrics.json
    metrics_data = {
        "schema": "loop-metrics/v1",
        "updated_at": "2026-09-01T00:00:00+00:00",
        "window_days": 7,
        "counters": {
            "sessions_total": 10,
            "tier0_attempts": 5,
            "tier0_success": 4,
            "tier0_fail": 1,
            "incidents_opened": 2,
            "incidents_escalated": 0,
            "check_after_halt": 1,
            "check_after_continue": 9,
            "tier1_attempts_total": 2,
            "tier1_resolved_total": 1,
        },
        "rates": {
            "tier0_success_rate": 0.8,
            "auto_continue_rate": 0.9,
            "tier1_success_rate": 0.5,
        },
        "entries": [],
    }
    (mb / "metrics.json").write_text(json.dumps(metrics_data), encoding="utf-8")

    # 2. incidents.jsonl
    inc1 = {
        "schema": "loop-incident/v1",
        "incident_id": "inc-001",
        "status": "open",
        "opened_at": "2026-09-01T00:00:00+00:00",
        "project_root": str(tmp_path),
        "epic_id": "T-HUB-038",
        "step_id": "s01",
        "phase": "BACK IMPLEMENT",
        "session_id": "sess-1",
        "source": "test",
        "fingerprint": "fp1",
    }
    inc2 = {
        "schema": "loop-incident/v1",
        "incident_id": "inc-002",
        "status": "resolved",
        "opened_at": "2026-09-01T00:00:00+00:00",
        "resolved_at": "2026-09-01T01:00:00+00:00",
        "project_root": str(tmp_path),
        "epic_id": "T-HUB-038",
        "step_id": "s01",
        "phase": "BACK IMPLEMENT",
        "session_id": "sess-1",
        "source": "test",
        "fingerprint": "fp2",
    }
    (mb / "incidents.jsonl").write_text(json.dumps(inc1) + "\n" + json.dumps(inc2) + "\n", encoding="utf-8")

    # 3. events.jsonl
    evt1 = {"kind": "incident_opened", "timestamp": "2026-09-01T00:00:00+00:00"}
    evt2 = {"kind": "incident_opened", "timestamp": "2026-09-01T00:05:00+00:00"}
    evt3 = {"kind": "tier0_repair_pass", "timestamp": "2026-09-01T00:10:00+00:00"}
    (mb / "events.jsonl").write_text("\n".join(json.dumps(e) for e in [evt1, evt2, evt3]), encoding="utf-8")

    # 4. tasks.md
    tasks_content = """# Tasks

## Active
| Epic | Role | Phase | Step | Title |
| --- | --- | --- | --- | --- |
| T-HUB-038 | back | IMPLEMENT | s01 | Harness metrics dashboard |
"""
    (mb / "tasks.md").write_text(tasks_content, encoding="utf-8")

    return tmp_path


def test_collect_returns_report(tmp_path: Path) -> None:
    root = _setup_fixture_dir(tmp_path)
    report = collect(root)

    assert isinstance(report, DashboardReport)
    assert report.schema_version == "dashboard-report/v1"
    assert len(report.open_incidents) == 1
    assert report.open_incidents[0].incident_id == "inc-001"
    assert len(report.epic_progress) == 1
    assert report.epic_progress[0].epic_id == "T-HUB-038"


def test_collect_rates_match_compute_rates(tmp_path: Path) -> None:
    root = _setup_fixture_dir(tmp_path)
    report = collect(root)

    expected_rates = compute_rates(report.metrics.counters)
    assert report.metrics.rates == expected_rates
    assert report.metrics.rates["tier0_success_rate"] == 0.8
    assert report.metrics.rates["auto_continue_rate"] == 0.9
    assert report.metrics.rates["tier1_success_rate"] == 0.5


def test_collect_events_by_kind(tmp_path: Path) -> None:
    root = _setup_fixture_dir(tmp_path)
    report = collect(root)

    assert report.events_by_kind.get("incident_opened") == 2
    assert report.events_by_kind.get("tier0_repair_pass") == 1
