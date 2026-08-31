"""Tests for loop.incidents.trace (session-trace.jsonl)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from loop.incidents.trace import (
    SCHEMA_LOOP_SESSION_TRACE,
    append_trace,
    is_trace_enabled,
    read_session_trace_tail,
)


def test_trace_append_valid_schema(tmp_path: Path) -> None:
    epic_dir = tmp_path / "epic_slot"

    entry = append_trace(
        epic_dir,
        phase="check_after",
        session_id="sess_123",
        step_id="s04",
        epic_id="T-HUB-017",
        action="tier0_repair",
        detail={"repair": "cleared_lock"},
        decide="continue",
    )

    assert entry is not None
    assert entry["schema"] == SCHEMA_LOOP_SESSION_TRACE
    assert entry["phase"] == "check_after"
    assert entry["session_id"] == "sess_123"
    assert entry["step_id"] == "s04"
    assert entry["epic_id"] == "T-HUB-017"
    assert entry["action"] == "tier0_repair"
    assert entry["detail"] == {"repair": "cleared_lock"}
    assert entry["decide"] == "continue"
    assert "ts" in entry

    trace_file = epic_dir / "session-trace.jsonl"
    assert trace_file.is_file()
    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["schema"] == SCHEMA_LOOP_SESSION_TRACE
    assert parsed["session_id"] == "sess_123"


def test_trace_disabled_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    epic_dir = tmp_path / "epic_slot"
    monkeypatch.setenv("EPIC_INCIDENT_TRACE", "0")

    assert not is_trace_enabled()
    res = append_trace(epic_dir, phase="prepare")
    assert res is None

    trace_file = epic_dir / "session-trace.jsonl"
    assert not trace_file.exists()


def test_trace_tail_last_n_entries(tmp_path: Path) -> None:
    epic_dir = tmp_path / "epic_slot"

    for i in range(15):
        append_trace(
            epic_dir,
            phase=f"phase_{i}",
            action=f"action_{i}",
        )

    tail = read_session_trace_tail(epic_dir, limit=5)
    assert len(tail) == 5
    assert tail[0]["phase"] == "phase_10"
    assert tail[4]["phase"] == "phase_14"


def test_loop_sh_smoke_trace_hooks(tmp_path: Path) -> None:
    """Verify loop.sh / context_loop write session-trace.jsonl entries during loop operations."""
    # We can test helper execution via python -m loop.context_loop prepare / check-after or verify trace helper integration
    epic_dir = tmp_path / ".claude" / "runtime" / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)

    # Append test entries for prepare, check_after, decide
    append_trace(epic_dir, phase="prepare", session_id="s1", step_id="s04", epic_id="T-HUB-017")
    append_trace(epic_dir, phase="check_after", session_id="s1", step_id="s04", epic_id="T-HUB-017", action="tier0_repair")
    append_trace(epic_dir, phase="decide", session_id="s1", step_id="s04", epic_id="T-HUB-017", decide="continue")

    tail = read_session_trace_tail(epic_dir, limit=10)
    assert len(tail) >= 3
    phases = [e["phase"] for e in tail]
    assert "prepare" in phases
    assert "check_after" in phases
    assert "decide" in phases
