"""Tests for test execution fingerprinting, caching, and invalidation on relevant change.
Addresses FR-006, AC 3, TM-078-05.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from context_scope import (
    TestFingerprintCache,
    compute_diff_fingerprint,
    compute_test_fingerprint,
    normalize_test_command,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_normalize_test_command():
    assert normalize_test_command(".venv/bin/pytest app/tests/test_foo.py -q") == "pytest app/tests/test_foo.py -q"
    assert normalize_test_command("python -m pytest -v") == "pytest -v"
    assert normalize_test_command("bin/pytest -k jump") == "pytest -k jump"


def test_test_fingerprint_cache_invalidates_on_relevant_change(workspace: Path):
    src_file = workspace / "app" / "service.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("def run(): return 1\n", encoding="utf-8")

    test_file = workspace / "tests" / "test_service.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_run(): assert True\n", encoding="utf-8")

    relevant = [str(src_file), str(test_file)]
    cmd = ".venv/bin/pytest tests/test_service.py -q"

    cache = TestFingerprintCache(project_root=workspace)

    # 1. Initial lookup -> miss
    initial_hit = cache.lookup(cmd, relevant_paths=relevant)
    assert initial_hit is None

    # 2. Record execution result
    fp1 = cache.record(cmd, exit_code=0, output_summary="1 passed in 0.05s", relevant_paths=relevant)
    assert fp1 is not None

    # 3. Exact repeat without changed inputs -> cache hit / no-op
    repeat_hit = cache.lookup(cmd, relevant_paths=relevant)
    assert repeat_hit is not None
    assert repeat_hit["cached"] is True
    assert repeat_hit["no_op"] is True
    assert repeat_hit["exit_code"] == 0
    assert repeat_hit["output_summary"] == "1 passed in 0.05s"
    assert repeat_hit["fingerprint"] == fp1

    # 4. Modify relevant source file -> cache miss (fingerprint changed)
    src_file.write_text("def run(): return 2\n", encoding="utf-8")
    miss_after_edit = cache.lookup(cmd, relevant_paths=relevant)
    assert miss_after_edit is None

    # 5. Record new execution result after modification
    fp2 = cache.record(cmd, exit_code=0, output_summary="1 passed in 0.04s", relevant_paths=relevant)
    assert fp2 != fp1

    # 6. Lookup now hits the new fingerprint
    hit_fp2 = cache.lookup(cmd, relevant_paths=relevant)
    assert hit_fp2 is not None
    assert hit_fp2["fingerprint"] == fp2

    # 7. Explicit path invalidation
    invalidated = cache.invalidate_path(src_file)
    assert len(invalidated) >= 1
    assert cache.lookup(cmd, relevant_paths=relevant) is None


def test_different_command_or_flags_yields_cache_miss(workspace: Path):
    f = workspace / "tests" / "test_a.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("def test_a(): pass\n", encoding="utf-8")

    cache = TestFingerprintCache(project_root=workspace)
    cmd1 = "pytest tests/test_a.py -k a"
    cmd2 = "pytest tests/test_a.py -k b"

    cache.record(cmd1, exit_code=0, output_summary="passed", relevant_paths=[f])
    assert cache.lookup(cmd1, relevant_paths=[f]) is not None
    assert cache.lookup(cmd2, relevant_paths=[f]) is None
