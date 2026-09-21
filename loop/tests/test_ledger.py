from __future__ import annotations

import json
from pathlib import Path

import pytest

from loop.kernel.boundary import BoundaryService
from loop.kernel.model import Cursor
from loop.kernel.store import LoopPaths


def _paths(tmp_path: Path) -> LoopPaths:
    (tmp_path / "memory-bank").mkdir()
    return LoopPaths(project=tmp_path, hub=tmp_path / "hub")


def _cursor(step: str = "s01") -> Cursor:
    return Cursor(epic_id="E1", step_id=step, phase="IMPLEMENT", session_id="session-1")


def _read(path: Path, *, actor: str | None = None, agent_type: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"tool_name": "Read", "file_path": str(path), "cwd": str(path.parent), "session_id": "session-1", "start_line": 1, "end_line": 3}
    if actor:
        payload["agent_invocation_id"] = actor
    if agent_type:
        payload["agent_type"] = agent_type
    return payload


def test_boundary_preserves_interval_receipts_and_actor_isolation(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    target = tmp_path / "source.py"
    target.write_text("1\n2\n3\n4\n5\n6\n", encoding="utf-8")
    boundary = BoundaryService(paths)
    cursor = _cursor()

    first = boundary.read(_read(target, actor="root"), cursor)
    duplicate = boundary.read(_read(target, actor="root"), cursor)
    partial_payload = _read(target, actor="root")
    partial_payload["start_line"] = 2
    partial_payload["end_line"] = 5
    partial = boundary.read(partial_payload, cursor)
    subagent = boundary.read(_read(target, agent_type="verify-implement"), cursor)

    assert first.decision == "allowed"
    assert duplicate.decision == "duplicate"
    assert not duplicate.allowed
    assert partial.decision == "partial"
    assert partial.allowed_intervals == [[4, 5]]
    assert subagent.decision == "allowed"
    assert first.actor["invocation_id"] != subagent.actor["invocation_id"]
    assert paths.boundary_state.is_file()
    state = json.loads(paths.boundary_state.read_text(encoding="utf-8"))
    assert "cursor" not in state
    assert state["scope_key"]


def test_change_invalidates_all_session_actors_and_new_step_resets_scope(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    target = tmp_path / "source.py"
    target.write_text("old\n", encoding="utf-8")
    boundary = BoundaryService(paths)
    cursor = _cursor()
    boundary.read(_read(target, actor="root"), cursor)
    boundary.read(_read(target, actor="worker"), cursor)
    boundary.ensure_step(cursor)
    boundary.change({"tool_name": "Edit", "file_path": str(target), "cwd": str(tmp_path), "session_id": "session-1", "agent_invocation_id": "root"}, cursor, stage="pre")
    target.write_text("new\n", encoding="utf-8")
    boundary.change({"tool_name": "Edit", "file_path": str(target), "cwd": str(tmp_path), "session_id": "session-1", "agent_invocation_id": "root"}, cursor, stage="post")

    reread = boundary.read(_read(target, actor="root"), cursor)
    assert reread.decision == "allowed"
    assert reread.metadata["invalidated"] is True
    assert boundary.touched_paths(cursor) == ["source.py"]

    next_cursor = _cursor("s02")
    boundary.ensure_step(next_cursor)
    assert boundary.touched_paths(next_cursor) == []


def test_boundary_rejects_cursor_copy_in_policy_state(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.boundary_state.parent.mkdir(parents=True, exist_ok=True)
    paths.boundary_state.write_text(
        json.dumps({"schema": "loop-boundary/v1", "cursor": {"epic_id": "E1"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="legacy cursor identity"):
        BoundaryService(paths).context(_cursor())
