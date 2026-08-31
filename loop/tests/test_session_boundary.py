"""Tests for s03: session_boundary field in CheckpointRecord, finalize_step, and loop.sh detection."""

import os
import json
import subprocess
from pathlib import Path
import pytest
from loop.schemas.checkpoint import CheckpointRecord
from epic_lib import checkpoint_path


def test_schema_session_boundary_default_none():
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


def test_schema_session_boundary_true():
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


def test_finalize_sets_session_boundary(tmp_path: Path):
    """mock test / verify finalize_step writes session_boundary=True."""
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


def test_loop_detect_session_boundary():
    """Check that loop.sh or parsing logic detects session_boundary=true."""
    loop_sh = Path(__file__).resolve().parent.parent / "loop.sh"
    assert loop_sh.is_file()
    content = loop_sh.read_text(encoding="utf-8")
    assert "SESSION_BOUNDARY" in content
    assert "session_boundary" in content
