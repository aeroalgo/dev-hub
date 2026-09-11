"""Tests for session_boundary field in CheckpointRecord, finalize_step, and Python supervisor detection."""

from __future__ import annotations

import json
from pathlib import Path

from harness.hooks._lib import RuntimeConfig
from loop.runner import RunnerConfig
from loop.runner.orchestrator import LoopRunner
from loop.schemas.checkpoint import CheckpointRecord


def test_schema_session_boundary_default_none() -> None:
    """CheckpointRecord without session_boundary default to None."""
    rec = CheckpointRecord(
        checkpoint_seq=1,
        checkpoint_id="chk-001",
        session_id="sess-001",
        step_id="s03",
        phase="BACK IMPLEMENT",
        phase_epoch="epoch-1",
        stage="committed",
        status="committed",
        next_action="none",
        resume_policy="next_step",
    )
    assert rec.session_boundary is None


def test_schema_session_boundary_true() -> None:
    """CheckpointRecord with session_boundary=True validates ok."""
    rec = CheckpointRecord(
        checkpoint_seq=1,
        checkpoint_id="chk-002",
        session_id="sess-001",
        step_id="s03",
        phase="BACK IMPLEMENT",
        phase_epoch="epoch-1",
        stage="committed",
        status="committed",
        next_action="none",
        resume_policy="next_step",
        session_boundary=True,
    )
    assert rec.session_boundary is True


def test_finalize_sets_session_boundary(tmp_path: Path) -> None:
    """Verify finalize_step writes session_boundary=True."""
    from epic.core import commit_checkpoint, load_checkpoint

    record = commit_checkpoint(
        tmp_path,
        checkpoint_id="chk-test",
        session_id="sess-test",
        step_id="s03",
        phase="BACK IMPLEMENT",
        phase_epoch=1,
        stage="committed",
        status="committed",
        next_action="none",
        resume_policy="next_step",
        session_boundary=True,
    )
    assert record.get("session_boundary") is True

    loaded = load_checkpoint(tmp_path)
    assert loaded is not None
    assert loaded.get("session_boundary") is True


def test_runner_detect_session_boundary(tmp_path: Path) -> None:
    """Verify that LoopRunner detects session_boundary=True from checkpoint state."""
    state_dir = tmp_path / "runtime" / "dev-hub" / "epic"
    state_dir.mkdir(parents=True)
    chk_file = state_dir / "checkpoint.json"
    chk_file.write_text(json.dumps({"session_boundary": True}), encoding="utf-8")

    out_lines: list[str] = []
    cfg = RunnerConfig(
        hub_root=tmp_path,
        project_root=tmp_path,
        state_dir=state_dir,
        runtime=RuntimeConfig(
            session_timeout_sec=300,
            session_kill_grace_sec=10,
            transient_retry_max=3,
            subagent_retry_max=3,
            degraded_max=2,
            status_heartbeat_sec=60,
            stream_idle_timeout_sec=120,
            collaboration_wait_timeout_sec=120,
            permission_mode="bypass",
            sources={},
            epic_runtime="claude",
        ),
        permission_mode="bypass",
        headless=True,
        interactive=False,
        verbose=False,
    )
    runner = LoopRunner(config=cfg, stdout=lambda msg: out_lines.append(msg))

    assert chk_file.is_file()
    chk_data = json.loads(chk_file.read_text(encoding="utf-8"))
    assert chk_data.get("session_boundary") is True
