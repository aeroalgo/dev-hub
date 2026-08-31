"""Tests for loop/incidents/metrics.py (rolling counters + rates)."""

from __future__ import annotations

import json
import os

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loop.incidents.metrics import (
    increment_counter,
    load_metrics,
    prune_metrics_entries,
    MetricsRecord,
)


def test_metrics_increment_counters(tmp_path: Path) -> None:
    rec1 = increment_counter(tmp_path, "sessions_total")
    assert rec1 is not None
    assert rec1.counters["sessions_total"] == 1

    rec2 = increment_counter(tmp_path, "sessions_total")
    assert rec2 is not None
    assert rec2.counters["sessions_total"] == 2

    loaded = load_metrics(tmp_path)
    assert loaded.counters["sessions_total"] == 2


def test_metrics_tier0_success_rate_two_of_three(tmp_path: Path) -> None:
    # 2 success, 1 fail -> 3 attempts
    increment_counter(tmp_path, "tier0_attempts")
    increment_counter(tmp_path, "tier0_success")

    increment_counter(tmp_path, "tier0_attempts")
    increment_counter(tmp_path, "tier0_success")

    increment_counter(tmp_path, "tier0_attempts")
    rec = increment_counter(tmp_path, "tier0_fail")

    assert rec is not None
    assert rec.counters["tier0_attempts"] == 3
    assert rec.counters["tier0_success"] == 2
    assert rec.counters["tier0_fail"] == 1
    # 2 / 3 = 0.6667 -> 0.67 or 0.6667
    assert round(rec.rates["tier0_success_rate"], 2) == 0.67


def test_metrics_rolling_window_prune(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=10)).isoformat()
    new_ts = (now - timedelta(days=1)).isoformat()

    # Old entry
    increment_counter(tmp_path, "tier0_attempts", timestamp=old_ts)
    increment_counter(tmp_path, "tier0_success", timestamp=old_ts)

    # New entry
    rec = increment_counter(tmp_path, "tier0_attempts", timestamp=new_ts)

    assert rec is not None
    # Old entries (10 days old) should have been pruned out of 7d window
    assert rec.counters["tier0_attempts"] == 1
    assert rec.counters["tier0_success"] == 0
    assert len(rec.entries) == 1


def test_metrics_atomic_write(tmp_path: Path) -> None:
    # Perform atomic increments
    increment_counter(tmp_path, "check_after_continue")
    metrics_file = tmp_path / "metrics.json"

    assert metrics_file.exists()
    # Ensure file parses cleanly
    content = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert content["schema"] == "loop-metrics/v1"
    assert content["counters"]["check_after_continue"] == 1
    assert content["rates"]["auto_continue_rate"] == 1.0


def test_metrics_disabled_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPIC_INCIDENT_METRICS", "0")

    result = increment_counter(tmp_path, "sessions_total")
    assert result is None

    metrics_file = tmp_path / "metrics.json"
    assert not metrics_file.exists()
