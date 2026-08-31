"""Git discipline module for atomic commits per sNN step."""

from __future__ import annotations

import os
import fnmatch
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field


class CommitResult(BaseModel):
    """Result of maybe_atomic_commit operation."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    ok: bool = True
    skipped: bool = False
    commit_sha: str | None = None
    error: str | None = None


def _is_dirty_unrelated(cwd: str | Path, allowlist: list[str] | None = None) -> bool:
    """Check if git repository has untracked or modified files not matching allowlist."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return True

    lines = res.stdout.splitlines()
    if not lines:
        return False

    if allowlist is None:
        allowlist = []

    for line in lines:
        if len(line) < 3:
            continue
        # Check index and worktree status codes
        # status codes: '?' = untracked, 'M' = modified, 'D' = deleted, 'A' = added
        filepath = line[3:].strip()

        # If file is untracked (??) or modified in worktree without being staged
        # Note: line[:2] contains status.
        # If there are changes that are not staged, or untracked files
        if line.startswith("??") or line[1] != " ":
            matched = False
            for pattern in allowlist:
                if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(Path(filepath).name, pattern):
                    matched = True
                    break

            if not matched:
                return True

    return False


def maybe_atomic_commit(
    cwd: str | Path,
    epic_id: str,
    step_id: str,
    title: str,
    allowlist: list[str] | None = None,
) -> CommitResult:
    """Perform atomic git commit if EPIC_ATOMIC_COMMIT env is enabled ("1" or "true")."""
    env_val = os.environ.get("EPIC_ATOMIC_COMMIT", "0").strip().lower()
    if env_val not in ("1", "true"):
        return CommitResult(ok=True, skipped=True)

    # Note: if allowlist is provided, we check for dirty files outside allowlist.
    # Otherwise, staged/unstaged changes for the current epic are expected to be committed via git add -A.
    # But untracked files outside allowlist when allowlist is specified or untracked dirty files are checked.
    # If allowlist is None (or empty), git add -A will add everything. If there's an untracked file outside allowlist, fail.
    if allowlist is not None and _is_dirty_unrelated(cwd, allowlist=allowlist):
        return CommitResult(
            ok=False,
            skipped=False,
            error="dirty tree with files outside allowlist",
        )

    # If allowlist is not passed, check if there are untracked dirty files if required by fail-closed policy:
    # Actually if allowlist is None, any untracked file is fine to be added by git add -A, unless dirty tree fail-closed check is active.
    # Let's check `_is_dirty_unrelated` when allowlist is given or when untracked files need filtering.

    commit_msg = f"{epic_id} {step_id}: {title}"
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        commit_res = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        rev_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        sha = rev_res.stdout.strip()
        return CommitResult(ok=True, skipped=False, commit_sha=sha)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else str(e)
        return CommitResult(ok=False, skipped=False, error=f"git commit failed: {err_msg}")
    except OSError as e:
        return CommitResult(ok=False, skipped=False, error=f"os error: {str(e)}")
