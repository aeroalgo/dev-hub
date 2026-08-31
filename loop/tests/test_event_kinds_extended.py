"""Tests for lifecycle event kinds extension (s04)."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import EVENT_KINDS, build_event, read_event_log_result
from epic import _append_event, reconcile_epic_events


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


def test_reconcile_epic_events_backfills_decompose_and_implement(tmp_path: Path) -> None:
    epic_id = "T-TEST-001"
    role_dir = "back"

    decomp_dir = tmp_path / "memory-bank" / role_dir / "plan" / f"decompose-{epic_id}"
    decomp_dir.mkdir(parents=True, exist_ok=True)
    s01_decomp = decomp_dir / "s01-foo.yaml"
    s01_decomp.write_text("schema: epic-decompose/v1\nstep_id: s01\n", encoding="utf-8")

    impl_dir = tmp_path / "memory-bank" / role_dir / "implement" / f"implement-{epic_id}"
    impl_dir.mkdir(parents=True, exist_ok=True)
    s01_impl = impl_dir / "s01-foo.yaml"
    s01_impl.write_text("schema: epic-implement/v1\nstep_id: s01\nstatus: completed\n", encoding="utf-8")

    events = reconcile_epic_events(tmp_path, role_dir, epic_id)
    kinds = [e["kind"] for e in events]
    assert "decompose_step_done" in kinds
    assert "implement_done" in kinds
