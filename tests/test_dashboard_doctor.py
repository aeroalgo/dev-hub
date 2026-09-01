"""Tests for loop doctor halt-rate warning check (s04)."""

import os
from pathlib import Path

from loop.incidents.doctor import _check_halt_rate, run_doctor
from loop.incidents.metrics import MetricsRecord, save_metrics_atomic, increment_counter


def test_halt_rate_warn(tmp_path: Path):
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\n1. test\n\n## Handoff\n- test\n")

    # Write metrics with check_after_halt=6, sessions_total=10 -> rate=0.6
    increment_counter(mb, "sessions_total", amount=10)
    increment_counter(mb, "check_after_halt", amount=6)

    res = _check_halt_rate(mb, threshold=0.5)
    assert res.status == "warn"
    assert "0.60" in res.detail or "0.6" in res.detail or "halt rate" in res.detail.lower()

    # Also check run_doctor integration
    os.environ["EPIC_DASHBOARD_HALT_WARN_RATE"] = "0.5"
    try:
        report = run_doctor(tmp_path)
        check = next((c for c in report.checklist if c.name == "halt_rate"), None)
        assert check is not None
        assert check.status == "warn"
        assert len(report.warnings) > 0
    finally:
        os.environ.pop("EPIC_DASHBOARD_HALT_WARN_RATE", None)


def test_halt_rate_ok(tmp_path: Path):
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\n1. test\n\n## Handoff\n- test\n")

    # Write metrics with check_after_halt=3, sessions_total=10 -> rate=0.3 <= 0.5
    increment_counter(mb, "sessions_total", amount=10)
    increment_counter(mb, "check_after_halt", amount=3)

    res = _check_halt_rate(mb, threshold=0.5)
    assert res.status == "pass"


def test_halt_rate_skip_no_metrics(tmp_path: Path):
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\n1. test\n\n## Handoff\n- test\n")

    res = _check_halt_rate(mb, threshold=0.5)
    assert res.status == "skipped"
    assert "metrics.json" in res.detail or "not found" in res.detail.lower()
