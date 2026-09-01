import os
from pathlib import Path
import pytest
import yaml
from unittest.mock import patch, MagicMock

from loop.parallel.orchestrator import run_parallel_wave, ParallelResult


def create_epic_fixture(tmp_path: Path):
    decompose_dir = tmp_path / "decompose"
    decompose_dir.mkdir()
    index_file = decompose_dir / "index.yaml"
    index_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-TEST-001
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
    depends_on: ["s01"]
  - id: s03
    file: s03.yaml
    title: Step 3
    next_phase: BACK IMPLEMENT
    status: pending
    depends_on: ["s01"]
""",
        encoding="utf-8",
    )

    s02_shard = decompose_dir / "s02.yaml"
    s02_shard.write_text(
        yaml.safe_dump({"context": {"files": ["file_a.py"]}}),
        encoding="utf-8",
    )

    s03_shard = decompose_dir / "s03.yaml"
    s03_shard.write_text(
        yaml.safe_dump({"context": {"files": ["file_b.py"]}}),
        encoding="utf-8",
    )

    return index_file, decompose_dir


def test_sequential_fallback_env(tmp_path: Path):
    index_file, _ = create_epic_fixture(tmp_path)
    res = run_parallel_wave("T-TEST-001", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "0"})
    assert res is None


@patch("loop.parallel.orchestrator.create_worktree")
@patch("loop.parallel.orchestrator.destroy_worktree")
@patch("asyncio.create_subprocess_exec")
def test_wave_spawn_count(mock_subproc, mock_destroy, mock_create, tmp_path: Path):
    index_file, _ = create_epic_fixture(tmp_path)
    mock_create.side_effect = lambda epic_id, step_id, repo_root: tmp_path / f"wt-{step_id}"

    mock_proc = MagicMock()
    async def dummy_communicate():
        return b"", b""
    mock_proc.communicate = dummy_communicate
    mock_proc.returncode = 0

    async def dummy_subproc(*args, **kwargs):
        return mock_proc

    mock_subproc.side_effect = dummy_subproc

    res = run_parallel_wave("T-TEST-001", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "1", "EPIC_PARALLEL_MAX": "2"})
    assert res is not None
    assert res.wave == ["s02", "s03"]
    assert res.spawned == ["s02", "s03"]
    assert res.failed == []
    assert mock_create.call_count == 2
    assert mock_destroy.call_count == 2


@patch("loop.parallel.orchestrator.create_worktree")
@patch("loop.parallel.orchestrator.destroy_worktree")
@patch("asyncio.create_subprocess_exec")
def test_overlap_sequential_fallback(mock_subproc, mock_destroy, mock_create, tmp_path: Path):
    index_file, decompose_dir = create_epic_fixture(tmp_path)
    # Make s03 overlap with s02
    s03_shard = decompose_dir / "s03.yaml"
    s03_shard.write_text(
        yaml.safe_dump({"context": {"files": ["file_a.py"]}}),
        encoding="utf-8",
    )

    mock_create.side_effect = lambda epic_id, step_id, repo_root: tmp_path / f"wt-{step_id}"

    mock_proc = MagicMock()
    async def dummy_communicate():
        return b"", b""
    mock_proc.communicate = dummy_communicate
    mock_proc.returncode = 0

    async def dummy_subproc(*args, **kwargs):
        return mock_proc

    mock_subproc.side_effect = dummy_subproc

    res = run_parallel_wave("T-TEST-001", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "1", "EPIC_PARALLEL_MAX": "2"})
    assert res is not None
    assert res.wave == ["s02", "s03"]
    assert res.spawned == ["s02"]
    assert res.failed == []
    assert mock_create.call_count == 1
    assert mock_destroy.call_count == 1


@patch("loop.parallel.orchestrator.create_worktree")
@patch("loop.parallel.orchestrator.destroy_worktree")
@patch("asyncio.create_subprocess_exec")
def test_max_parallel_cap(mock_subproc, mock_destroy, mock_create, tmp_path: Path):
    index_file, _ = create_epic_fixture(tmp_path)
    mock_create.side_effect = lambda epic_id, step_id, repo_root: tmp_path / f"wt-{step_id}"

    mock_proc = MagicMock()
    async def dummy_communicate():
        return b"", b""
    mock_proc.communicate = dummy_communicate
    mock_proc.returncode = 0

    async def dummy_subproc(*args, **kwargs):
        return mock_proc

    mock_subproc.side_effect = dummy_subproc

    res = run_parallel_wave("T-TEST-001", index_file, tmp_path, env={"EPIC_PARALLEL_SNN": "1", "EPIC_PARALLEL_MAX": "1"})
    assert res is not None
    assert res.wave == ["s02", "s03"]
    assert res.spawned == ["s02"]
    assert mock_create.call_count == 1


def test_result_dataclass_fields():
    res = ParallelResult(wave=["s01"], spawned=["s01"], failed=[])
    assert res.wave == ["s01"]
    assert res.spawned == ["s01"]
    assert res.failed == []
