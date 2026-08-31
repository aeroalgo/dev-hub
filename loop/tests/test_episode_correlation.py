"""Tests for episode correlation in trace entries and incident metadata (T-HUB-031 s04)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.incidents.schema import IncidentRecord
from loop.incidents.trace import (
    SCHEMA_LOOP_SESSION_TRACE,
    append_trace,
    read_session_trace_tail,
)
from loop.context_loop import _run_tier0_check_after
from epic_lib import save_epic_state, load_epic_state


def test_trace_entry_has_episode_id(tmp_path: Path) -> None:
    epic_dir = tmp_path / "epic_slot"

    entry = append_trace(
        epic_dir,
        phase="check_after",
        session_id="sess_123",
        step_id="s04",
        epic_id="T-HUB-031",
        episode_id="ep-001",
        action="tier0_repair",
    )

    assert entry is not None
    assert entry["episode_id"] == "ep-001"

    trace_file = epic_dir / "session-trace.jsonl"
    assert trace_file.is_file()
    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed.get("episode_id") == "ep-001"


def test_trace_entry_no_episode_id_backward_compat(tmp_path: Path) -> None:
    epic_dir = tmp_path / "epic_slot"

    entry = append_trace(
        epic_dir,
        phase="check_after",
        session_id="sess_123",
        step_id="s04",
        epic_id="T-HUB-031",
        action="tier0_repair",
    )

    assert entry is not None
    assert "episode_id" not in entry

    trace_file = epic_dir / "session-trace.jsonl"
    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    parsed = json.loads(lines[0])
    assert "episode_id" not in parsed


def test_incident_has_episode_id(tmp_path: Path) -> None:
    act_ctx = tmp_path / "memory-bank" / "activeContext.md"
    act_ctx.parent.mkdir(parents=True, exist_ok=True)
    act_ctx.write_text("## load_now\n1. test\n\n## Handoff\n- test\n", encoding="utf-8")

    # Setup epic state with episode_id
    st = {
        "armed_epic": "T-HUB-031",
        "role": "back",
        "armed_step": "s04",
        "episode_id": "ep-999",
    }
    save_epic_state(tmp_path, st)

    res_input = {
        "ok": False,
        "diagnostic_code": "test_failure_code",
    }

    _run_tier0_check_after(tmp_path, res_input)

    # Check that open incident has episode_id in metadata
    from loop.incidents.store import list_open_incidents
    from epic_paths import epic_dir

    edir = epic_dir(tmp_path)
    open_incs = list_open_incidents(edir)
    target_incs = [i for i in open_incs if "test_failure_code" in i.diagnostic_codes]
    assert len(target_incs) == 1
    assert target_incs[0].metadata.get("episode_id") == "ep-999"


def test_append_event_forwards_episode_id(tmp_path: Path) -> None:
    epic_dir = tmp_path / "epic_slot"
    entry = append_trace(
        epic_dir,
        phase="prepare",
        session_id="sess_abc",
        step_id="s04",
        epic_id="T-HUB-031",
        episode_id="ep-555",
        action="prepare_session",
    )
    assert entry is not None
    assert entry.get("episode_id") == "ep-555"
