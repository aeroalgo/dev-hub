"""Tests for lifecycle event kinds extension (s04)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import EVENT_KINDS, build_event, read_event_log_result
from epic import _append_event


def test_event_kinds_contains_5_new_kinds() -> None:
    new_kinds = {
        "implement_done",
        "decompose_step_done",
        "phase_transition",
        "traceability_warn",
        "traceability_fail",
    }
    assert new_kinds.issubset(EVENT_KINDS)


def test_append_event_accepts_new_kinds(tmp_path: Path) -> None:
    art = tmp_path / "art.txt"
    art.write_text("hello", encoding="utf-8")
    for kind in [
        "implement_done",
        "decompose_step_done",
        "phase_transition",
        "traceability_warn",
        "traceability_fail",
    ]:
        res = _append_event(tmp_path, "back", "T-HUB-030", kind, art)
        assert res is True

    path = tmp_path / "memory-bank" / "back" / "events" / "T-HUB-030" / "events.jsonl"
    log = read_event_log_result(path, expected_epic_id="T-HUB-030", cwd=tmp_path)
    assert log.ok is True
    assert len(log.events) == 5
    kinds = [e["kind"] for e in log.events]
    assert kinds == [
        "implement_done",
        "decompose_step_done",
        "phase_transition",
        "traceability_warn",
        "traceability_fail",
    ]
