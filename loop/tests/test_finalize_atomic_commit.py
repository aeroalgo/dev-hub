"""Tests for finalize_step atomic commit integration (s02)."""

import os
import sys
from pathlib import Path
from typing import Any
import pytest

ROOT = Path(__file__).resolve().parents[2]
hooks_dir = str(ROOT / ".claude" / "hooks")
if hooks_dir not in sys.path:
    sys.path.insert(0, hooks_dir)

from epic import finalize_step, save_epic_state
from loop.git_discipline import CommitResult


def _setup_decompose_and_implement(tmp_path: Path) -> tuple[Path, str]:
    """Helper to set up a dummy decompose index and implement shard in tmp_path."""
    mb = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-999"
    mb.mkdir(parents=True, exist_ok=True)
    idx_path = mb / "index.yaml"
    idx_content = """schema: epic-decompose-index/v1
plan_id: T-HUB-999
role: back
steps:
- id: s01
  file: s01-test.yaml
  title: Test Step 1
  status: pending
"""
    idx_path.write_text(idx_content, encoding="utf-8")

    shard_path = mb / "s01-test.yaml"
    shard_content = """schema: epic-decompose/v1
role: back
step_id: s01
plan_id: T-HUB-999
title: Test Step 1
checkpoints:
- id: cp1
  status: done
"""
    shard_path.write_text(shard_content, encoding="utf-8")

    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-999"
    impl_dir.mkdir(parents=True, exist_ok=True)
    impl_path = impl_dir / "s01-test.yaml"
    impl_content = """schema: epic-implement/v1
role: back
step_id: s01
plan_id: T-HUB-999
title: Test Step 1
status: in_progress
date: '2026-08-31'
decompose_ref: memory-bank/back/plan/decompose-T-HUB-999/s01-test.yaml
done:
- Done item 1
files:
- .claude/hooks/epic/core.py
tests:
- '`timeout 300s .venv/bin/pytest loop/tests/test_finalize_atomic_commit.py -q`'
integration_check:
- '`pytest` check ok'
checkpoints:
- id: cp1
  criterion: dummy criterion
  status: done
"""
    impl_path.write_text(impl_content, encoding="utf-8")

    # Mirror verify pass so require_verify passes
    st = {
        "last_verify_verdict": "PASS",
        "last_verify_at": "2026-08-31T00:00:00Z",
        "last_verify_evidence": "test evidence",
        "last_verify_step_id": "s01",
    }
    save_epic_state(tmp_path, st)

    return idx_path, "s01"


def test_finalize_atomic_commit_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "0")
    idx_path, step_id = _setup_decompose_and_implement(tmp_path)

    res = finalize_step(tmp_path, idx_path, step_id, require_verify=False)
    assert res.get("ok") is True
    assert "atomic_commit" in res
    assert res["atomic_commit"]["skipped"] is True
    assert res["atomic_commit"]["ok"] is True


def test_finalize_atomic_commit_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    idx_path, step_id = _setup_decompose_and_implement(tmp_path)

    def mock_maybe_commit(cwd: Any, epic_id: str, step_id: str, title: str, allowlist: Any = None) -> CommitResult:
        assert epic_id == "T-HUB-999"
        assert step_id == "s01"
        assert title == "Test Step 1"
        return CommitResult(ok=True, skipped=False, commit_sha="abc123def")

    monkeypatch.setattr("loop.git_discipline.maybe_atomic_commit", mock_maybe_commit)

    res = finalize_step(tmp_path, idx_path, step_id, require_verify=False)
    assert res.get("ok") is True
    assert "atomic_commit" in res
    assert res["atomic_commit"]["ok"] is True
    assert res["atomic_commit"]["skipped"] is False
    assert res["atomic_commit"]["commit_sha"] == "abc123def"


def test_finalize_atomic_commit_fail_best_effort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    idx_path, step_id = _setup_decompose_and_implement(tmp_path)

    def mock_maybe_commit_raise(*args: Any, **kwargs: Any) -> CommitResult:
        raise RuntimeError("git failed unexpectedly")

    monkeypatch.setattr("loop.git_discipline.maybe_atomic_commit", mock_maybe_commit_raise)

    res = finalize_step(tmp_path, idx_path, step_id, require_verify=False)
    assert res.get("ok") is True
    assert "atomic_commit" in res
    assert res["atomic_commit"]["ok"] is False
    assert "git failed unexpectedly" in res["atomic_commit"]["error"]


def test_finalize_no_commit_key_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EPIC_ATOMIC_COMMIT", raising=False)
    idx_path, step_id = _setup_decompose_and_implement(tmp_path)

    res = finalize_step(tmp_path, idx_path, step_id, require_verify=False)
    assert res.get("ok") is True
    assert "atomic_commit" in res
    assert res["atomic_commit"]["skipped"] is True
