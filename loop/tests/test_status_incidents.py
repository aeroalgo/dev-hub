"""Tests for loop status incident, metric, and trace_tail integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import pytest

from epic_paths import epic_dir as get_epic_dir
from loop.context_loop import status
from loop.incidents.metrics import increment_counter
from loop.incidents.schema import IncidentRecord
from loop.incidents.store import _write_incidents_jsonl
from loop.incidents.trace import append_trace


@pytest.fixture
def epic_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary runtime epic directory."""
    active_ctx = tmp_path / "memory-bank" / "activeContext.md"
    active_ctx.parent.mkdir(parents=True, exist_ok=True)
    active_ctx.write_text("# Active Context\n", encoding="utf-8")
    return get_epic_dir(tmp_path)


def test_status_incidents_open_count(tmp_path: Path, epic_dir: Path) -> None:
    incidents = [
        IncidentRecord(
            incident_id=f"INC-{i:03d}",
            opened_at=f"2026-08-30T10:0{i}:00Z",
            project_root=str(tmp_path),
            epic_id="test-epic",
            step_id=f"s{i:02d}",
            phase="BACK IMPLEMENT",
            session_id="sess-1",
            source="check_after",
            fingerprint=f"fp-{i}",
            diagnostic_codes=["tier0_fail"],
            status="open" if i <= 3 else "resolved",
        )
        for i in range(1, 7)
    ]
    _write_incidents_jsonl(epic_dir / "incidents.jsonl", incidents)

    res = status(tmp_path)
    assert "incidents" in res
    assert res["incidents"]["open_count"] == 3
    assert len(res["incidents"]["last"]) == 3
    assert res["incidents"]["last"][0]["incident_id"] == "INC-001"
    # Ensure no secrets leak
    for item in res["incidents"]["last"]:
        assert "prompt" not in item
        assert "secrets" not in item


def test_status_metrics_summary(tmp_path: Path, epic_dir: Path) -> None:
    increment_counter(epic_dir, "tier0_attempts", amount=10)
    increment_counter(epic_dir, "tier0_success", amount=8)
    increment_counter(epic_dir, "tier0_fail", amount=2)

    res = status(tmp_path)
    assert "metrics" in res
    metrics_summary = res["metrics"]
    assert metrics_summary["counters"]["tier0_attempts"] == 10
    assert metrics_summary["counters"]["tier0_success"] == 8
    assert metrics_summary["rates"]["tier0_success_rate"] == 0.8


def test_status_trace_tail_bounded(tmp_path: Path, epic_dir: Path) -> None:
    for i in range(1, 15):
        append_trace(
            epic_dir,
            phase="BACK IMPLEMENT",
            session_id=f"sess-{i}",
            step_id=f"s{i:02d}",
            epic_id="test-epic",
            action=f"action-{i}",
            detail={"secret_prompt": "do not expose me", "info": f"step-{i}"},
        )

    res = status(tmp_path)
    assert "trace_tail" in res
    trace_tail = res["trace_tail"]
    assert len(trace_tail) == 10
    assert trace_tail[-1]["action"] == "action-14"


def test_status_no_secrets_in_payload(tmp_path: Path, epic_dir: Path) -> None:
    append_trace(
        epic_dir,
        phase="BACK IMPLEMENT",
        session_id="sess-1",
        step_id="s01",
        epic_id="test-epic",
        action="action-secret",
        detail={"prompt": "SUPER_SECRET_PROMPT_KEY", "secrets": "API_KEY_12345"},
    )

    res = status(tmp_path)
    payload_str = json.dumps(res)
    assert "SUPER_SECRET_PROMPT_KEY" not in payload_str
    assert "API_KEY_12345" not in payload_str


def test_status_corrupt_incidents_flag(tmp_path: Path, epic_dir: Path) -> None:
    incidents_path = epic_dir / "incidents.jsonl"
    incidents_path.write_text("CORRUPT_NON_JSON_LINE\n", encoding="utf-8")

    res = status(tmp_path)
    assert "incidents" in res
    assert res["incidents"].get("incidents_corrupt") is True
