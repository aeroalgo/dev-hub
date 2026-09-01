import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Optional

WORKTREE_BASE_NAME = ".claude/worktrees"


def create_worktree(
    epic_id: str,
    step_id: str,
    repo_root: Path,
    base_ref: str = "HEAD",
) -> Path:
    """
    Creates a new git worktree under repo_root / .claude / worktrees / <epic_id>-<step_id>-<timestamp>.
    Runs `git worktree add <target_dir> <base_ref>` using subprocess.
    """
    ts = int(time.time() * 1000)
    target_dir = repo_root / WORKTREE_BASE_NAME / f"{epic_id}-{step_id}-{ts}"
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "worktree", "add", str(target_dir), base_ref]
    res = subprocess.run(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to create worktree: {res.stderr}")

    return target_dir


def destroy_worktree(path: Path, repo_root: Path) -> None:
    """
    Removes a git worktree using `git worktree remove --force <path>`.
    """
    cmd = ["git", "worktree", "remove", "--force", str(path)]
    res = subprocess.run(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to destroy worktree: {res.stderr}")


def list_epic_worktrees(epic_id: str, repo_root: Path) -> List[Path]:
    """
    Parses `git worktree list --porcelain` output to find paths matching epic_id.
    """
    cmd = ["git", "worktree", "list", "--porcelain"]
    res = subprocess.run(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Failed to list worktrees: {res.stderr}")

    paths: List[Path] = []
    for line in res.stdout.splitlines():
        if line.startswith("worktree "):
            wt_path_str = line[len("worktree ") :].strip()
            wt_path = Path(wt_path_str)
            if f"{epic_id}-" in wt_path.name:
                paths.append(wt_path)

    return paths
