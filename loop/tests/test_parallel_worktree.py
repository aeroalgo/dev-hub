from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from loop.parallel.worktree import (
    create_worktree,
    destroy_worktree,
    list_epic_worktrees,
)


def test_create_worktree_subprocess(tmp_path: Path):
    repo_root = tmp_path
    epic_id = "T-HUB-037"
    step_id = "s03"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res_path = create_worktree(epic_id, step_id, repo_root)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "git"
        assert cmd[1] == "worktree"
        assert cmd[2] == "add"
        assert str(res_path) in cmd[3]
        assert cmd[4] == "HEAD"


def test_destroy_worktree_subprocess(tmp_path: Path):
    repo_root = tmp_path
    wt_path = repo_root / ".claude/worktrees/T-HUB-037-s03-12345"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        destroy_worktree(wt_path, repo_root)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "git"
        assert cmd[1] == "worktree"
        assert cmd[2] == "remove"
        assert cmd[3] == "--force"
        assert cmd[4] == str(wt_path)


def test_worktree_path_contains_ids(tmp_path: Path):
    repo_root = tmp_path
    epic_id = "T-HUB-037"
    step_id = "s03"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res_path = create_worktree(epic_id, step_id, repo_root)

        assert f"{epic_id}-{step_id}-" in res_path.name


def test_list_epic_worktrees_empty(tmp_path: Path):
    repo_root = tmp_path
    epic_id = "T-HUB-037"

    porcelain_output = (
        f"worktree {tmp_path}\nHEAD 12345\nbranch refs/heads/master\n\n"
        f"worktree {tmp_path}/.claude/worktrees/T-HUB-038-s01-100\nHEAD 12345\nbranch refs/heads/other\n\n"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=porcelain_output, stderr=""
        )
        res = list_epic_worktrees(epic_id, repo_root)
        assert res == []


def test_list_epic_worktrees_found(tmp_path: Path):
    repo_root = tmp_path
    epic_id = "T-HUB-037"

    wt1 = tmp_path / ".claude/worktrees/T-HUB-037-s01-100"
    wt2 = tmp_path / ".claude/worktrees/T-HUB-037-s02-200"

    porcelain_output = (
        f"worktree {tmp_path}\nHEAD 12345\n\n"
        f"worktree {wt1}\nHEAD 12345\n\n"
        f"worktree {wt2}\nHEAD 12345\n\n"
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=porcelain_output, stderr=""
        )
        res = list_epic_worktrees(epic_id, repo_root)
        assert res == [wt1, wt2]
