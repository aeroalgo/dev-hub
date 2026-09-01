import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import yaml

from loop.epic_transition import arm_phase
from loop.parallel.orchestrator import run_parallel_wave, ParallelResult


def test_parallel_branch_activated(monkeypatch, tmp_path):
    def mock_run(epic_id, index_path, repo_root, env=None):
        return ParallelResult(wave=["s02", "s03"], spawned=["s02", "s03"], failed=[])

    monkeypatch.setattr("loop.parallel.orchestrator.run_parallel_wave", mock_run)

    decompose_dir = tmp_path / "decompose"
    decompose_dir.mkdir(parents=True, exist_ok=True)
    index_file = decompose_dir / "index.yaml"
    index_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-HUB-037
steps:
  - id: s01
    file: s01.yaml
    status: completed
  - id: s02
    file: s02.yaml
    status: pending
"""
    )

    env = {"EPIC_PARALLEL_SNN": "1"}
    res = arm_phase(tmp_path, "T-HUB-037", "IMPLEMENT", "back", decompose_rel="decompose/index.yaml", env=env)
    assert res.get("parallel") is True
    assert res.get("wave") == ["s02", "s03"]
    assert res.get("spawned") == ["s02", "s03"]


def test_sequential_env_zero(monkeypatch, tmp_path):
    called = False

    def mock_run(epic_id, index_path, repo_root, env=None):
        nonlocal called
        called = True
        return ParallelResult(wave=["s02"], spawned=["s02"], failed=[])

    monkeypatch.setattr("loop.parallel.orchestrator.run_parallel_wave", mock_run)

    monkeypatch.setenv("EPIC_PARALLEL_SNN", "0")
    res = arm_phase(tmp_path, "T-HUB-037", "IMPLEMENT", "back")
    assert not called
    assert res.get("parallel") is not True


def test_no_parallel_for_plan_step(monkeypatch, tmp_path):
    called = False

    def mock_run(epic_id, index_path, repo_root, env=None):
        nonlocal called
        called = True
        return ParallelResult(wave=["s02"], spawned=["s02"], failed=[])

    monkeypatch.setattr("loop.parallel.orchestrator.run_parallel_wave", mock_run)

    env = {"EPIC_PARALLEL_SNN": "1"}
    res = arm_phase(tmp_path, "T-HUB-037", "PLAN", "back", env=env)
    assert not called
    assert res.get("parallel") is not True


@patch("loop.parallel.orchestrator.create_worktree")
@patch("loop.parallel.orchestrator.asyncio.create_subprocess_exec")
def test_sc001_two_independent_steps(mock_subproc, mock_create, tmp_path):
    decompose_dir = tmp_path / "decompose"
    decompose_dir.mkdir(parents=True, exist_ok=True)
    index_file = decompose_dir / "index.yaml"
    index_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-HUB-037
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: completed
  - id: s02
    file: s02.yaml
    title: Step 2
    next_phase: BACK IMPLEMENT
    status: pending
  - id: s03
    file: s03.yaml
    title: Step 3
    next_phase: BACK IMPLEMENT
    status: pending
"""
    )
    (decompose_dir / "s01.yaml").write_text("delta:\n  - file1.py\n")
    (decompose_dir / "s02.yaml").write_text("delta:\n  - file2.py\n")
    (decompose_dir / "s03.yaml").write_text("delta:\n  - file3.py\n")

    mock_create.return_value = tmp_path / ".worktrees" / "s02"

    mock_proc = MagicMock()

    async def dummy_communicate():
        return b"", b""

    mock_proc.communicate = dummy_communicate
    mock_proc.returncode = 0

    async def dummy_subproc(*args, **kwargs):
        return mock_proc

    mock_subproc.side_effect = dummy_subproc

    res = run_parallel_wave("T-HUB-037", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "1"})
    assert res is not None
    assert res.wave == ["s02", "s03"]
    assert len(res.spawned) == 2
    assert res.failed == []


@patch("loop.parallel.orchestrator.create_worktree")
@patch("loop.parallel.orchestrator.asyncio.create_subprocess_exec")
def test_sc002_overlap_blocks_parallel(mock_subproc, mock_create, tmp_path):
    decompose_dir = tmp_path / "decompose"
    decompose_dir.mkdir(parents=True, exist_ok=True)
    index_file = decompose_dir / "index.yaml"
    index_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-HUB-037
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: completed
  - id: s02
    file: s02.yaml
    title: Step 2
    next_phase: BACK IMPLEMENT
    status: pending
  - id: s03
    file: s03.yaml
    title: Step 3
    next_phase: BACK IMPLEMENT
    status: pending
"""
    )
    (decompose_dir / "s01.yaml").write_text("delta:\n  - file1.py\n")
    (decompose_dir / "s02.yaml").write_text("delta:\n  - shared.py\n")
    (decompose_dir / "s03.yaml").write_text("delta:\n  - shared.py\n")

    mock_create.return_value = tmp_path / ".worktrees" / "s02"

    mock_proc = MagicMock()

    async def dummy_communicate():
        return b"", b""

    mock_proc.communicate = dummy_communicate
    mock_proc.returncode = 0

    async def dummy_subproc(*args, **kwargs):
        return mock_proc

    mock_subproc.side_effect = dummy_subproc

    res = run_parallel_wave("T-HUB-037", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "1"})
    assert res is not None
    assert res.wave == ["s02", "s03"]
    assert res.spawned == ["s02"]
    assert res.failed == []


def test_sc003_epic_parallel_zero_unchanged(tmp_path):
    decompose_dir = tmp_path / "decompose"
    decompose_dir.mkdir(parents=True, exist_ok=True)
    index_file = decompose_dir / "index.yaml"
    index_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-HUB-037
steps:
  - id: s01
    file: s01.yaml
    status: pending
"""
    )
    res = run_parallel_wave("T-HUB-037", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "0"})
    assert res is None
