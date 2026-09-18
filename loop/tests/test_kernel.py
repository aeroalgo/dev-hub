from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.model import CursorStatus
from loop.kernel.store import LoopPaths


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_project(root: Path) -> LoopPaths:
    write(root / "memory-bank/back/plan/E1/yaml/decompose-index.yaml", """
schema: epic-decompose-index/v1
epic_id: E1
steps:
  - id: s01
    file: s01-one.yaml
    status: pending
  - id: s02
    file: s02-two.yaml
    status: pending
""")
    write(root / "memory-bank/back/plan/E1/yaml/s01-one.yaml", "step_id: s01\n")
    write(root / "memory-bank/back/plan/E1/yaml/s02-two.yaml", "step_id: s02\n")
    return LoopPaths(project=root, hub=root / "hub")


def test_cursor_is_the_only_runtime_state_and_finish_advances_index(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)

    cursor = engine.start("E1")
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"
    assert paths.cursor.is_file()
    assert not (paths.runtime / "state.json").exists()
    assert not (paths.runtime / "checkpoint.json").exists()
    assert not (paths.runtime / "last-session.json").exists()

    transition = engine.finish(step_id="s01")
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text()
    assert "id: s01" in index and "status: completed" in index


def test_lifecycle_has_one_transition_path(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.finish(step_id="s01")
    engine.finish(step_id="s02")
    assert engine.store.read().phase == "AUDIT"

    write(tmp_path / "memory-bank/back/audit/E1/audit.yaml", "schema: audit\nverdict: pass\n")
    engine.finish(step_id="AUDIT")
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa.yaml", "schema: qa\nverdict: fail\n")
    engine.finish(step_id="QA")
    assert engine.store.read().phase == "BUGFIX"

    write(tmp_path / "memory-bank/back/bugfix/E1/fix.yaml", "schema: bugfix\nstatus: completed\n")
    engine.finish(step_id="BUGFIX")
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa.yaml", "schema: qa\nverdict: pass\n")
    engine.finish(step_id="QA")
    assert engine.store.read().status == CursorStatus.COMPLETE


def test_retry_is_bounded_by_one_counter(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    first = engine.retry("runtime_exit_1")
    second = engine.retry("runtime_exit_2")
    assert first.attempt == 1
    assert second.attempt == 2
    payload = json.loads(paths.cursor.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema",
        "revision",
        "epic_id",
        "role",
        "phase",
        "step_id",
        "status",
        "attempt",
        "session_id",
        "last_error",
        "updated_at",
    }


def test_phase_finish_requires_evidence_and_halt_is_terminal(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    engine.finish(step_id="s01")
    engine.finish(step_id="s02")

    with pytest.raises(TransitionError, match="audit artifact"):
        engine.finish(step_id="AUDIT")

    halted = engine.halt("manual stop")
    assert halted.status == CursorStatus.HALTED
    with pytest.raises(TransitionError, match="halted"):
        engine.finish(step_id="AUDIT")
