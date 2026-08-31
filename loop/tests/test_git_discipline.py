"""Tests for loop.git_discipline module."""

import os
import subprocess
from pathlib import Path
import pytest

from loop.git_discipline import maybe_atomic_commit, CommitResult, _is_dirty_unrelated


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Fixture providing a temporary clean git repository."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    # Initial commit so HEAD exists
    initial_file = tmp_path / "README.md"
    initial_file.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    return tmp_path


def test_skip_when_env_zero(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "0")
    res = maybe_atomic_commit(temp_git_repo, "T-HUB-033", "s01", "test title")
    assert res.skipped is True
    assert res.ok is True
    assert res.commit_sha is None


def test_commit_on_success(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    new_file = temp_git_repo / "foo.txt"
    new_file.write_text("hello")

    res = maybe_atomic_commit(temp_git_repo, "T-HUB-033", "s01", "test title")
    assert res.ok is True
    assert res.skipped is False
    assert res.commit_sha is not None

    log_res = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=str(temp_git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    assert log_res.stdout.strip() == "T-HUB-033 s01: test title"


def test_fail_on_dirty_tree(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    dirty_file = temp_git_repo / "untracked.txt"
    dirty_file.write_text("untracked content")

    res = maybe_atomic_commit(
        temp_git_repo,
        "T-HUB-033",
        "s01",
        "test title",
        allowlist=["*.py", "*.md"],
    )
    assert res.ok is False
    assert res.skipped is False
    assert res.error is not None
    assert "dirty" in res.error.lower()


def test_commit_message_format(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    (temp_git_repo / "bar.py").write_text("print('hello')")

    res = maybe_atomic_commit(temp_git_repo, "EPIC-100", "s05", "Refactor module")
    assert res.ok is True

    log_res = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=str(temp_git_repo),
        capture_output=True,
        text=True,
        check=True,
    )
    assert log_res.stdout.strip() == "EPIC-100 s05: Refactor module"


def test_allowlist_passes_dirty(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EPIC_ATOMIC_COMMIT", "1")
    (temp_git_repo / "doc.md").write_text("some docs")

    res = maybe_atomic_commit(
        temp_git_repo,
        "T-HUB-033",
        "s01",
        "test title",
        allowlist=["*.md"],
    )
    assert res.ok is True
    assert res.skipped is False
