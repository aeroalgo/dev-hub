"""Janitor GC whitelist-only repair engine."""

from __future__ import annotations

import fnmatch
import shutil
import sys
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic_lib import repair_index_mirror  # noqa: E402
from loop.janitor.schema import JanitorFinding  # noqa: E402


class GcWhitelistError(Exception):
    """Raised when a repair target path is not in the whitelist (SC-002, NFR-02)."""

    pass


class GcResult(BaseModel):
    """Result of GcEngine repair action."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    success: bool = True
    dry_run: bool = True
    action: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


DEFAULT_WHITELIST_PATTERNS = [
    "memory-bank/*/plan/decompose-*/index.md",
    "memory-bank/*/plan/*/md/decompose-index.md",
    "runtime/episodes/*",
    "runtime/episodes",
    "episodes/*",
    "episodes",
    "runtime/events/*",
    "runtime/events",
    "events/*",
    "events",
]


class GcEngine:
    """Whitelist-only bounded repairs engine for Janitor findings."""

    def __init__(
        self,
        cwd: str | Path | None = None,
        whitelist_patterns: list[str] | None = None,
    ) -> None:
        self.cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        self.whitelist_patterns = (
            whitelist_patterns
            if whitelist_patterns is not None
            else DEFAULT_WHITELIST_PATTERNS
        )

    def is_whitelisted(self, rel_or_abs_path: str | Path) -> bool:
        """Check if path matches any pattern in whitelist_patterns."""
        path_p = Path(rel_or_abs_path)
        if path_p.is_absolute():
            try:
                rel_path_str = str(path_p.relative_to(self.cwd))
            except ValueError:
                return False
        else:
            rel_path_str = str(path_p)

        # Normalize path separators for fnmatch
        rel_path_str = rel_path_str.replace("\\", "/")

        for pattern in self.whitelist_patterns:
            pattern_norm = pattern.replace("\\", "/")
            if fnmatch.fnmatch(rel_path_str, pattern_norm):
                return True
            # Check prefix matching for wildcards / directories
            if pattern_norm.endswith("/*"):
                prefix = pattern_norm[:-2]
                if rel_path_str == prefix or rel_path_str.startswith(prefix + "/"):
                    return True
        return False

    def apply_repair(
        self, finding: JanitorFinding, dry_run: bool = True
    ) -> GcResult:
        """Apply bounded repair for a JanitorFinding with whitelist fail-closed enforcement."""
        target_path_str = finding.target_path
        target_full_path = (self.cwd / target_path_str).resolve()

        # Fail-closed whitelist check (SC-002, NFR-02)
        if not self.is_whitelisted(target_path_str) and not self.is_whitelisted(target_full_path):
            raise GcWhitelistError(
                f"Target path '{target_path_str}' is not in the whitelist patterns: {self.whitelist_patterns}"
            )

        cat = finding.category

        if cat == "stale_index_status":
            # Action: index_mirror_patch
            if dry_run:
                return GcResult(
                    success=True,
                    dry_run=True,
                    action="index_mirror_patch",
                    target_path=target_path_str,
                    details={"status": "dry_run_skipped_write"},
                )

            # Repair call using epic_lib repair_index_mirror
            res = repair_index_mirror(self.cwd, target_path_str)
            return GcResult(
                success=True,
                dry_run=False,
                action="index_mirror_patch",
                target_path=target_path_str,
                details={"repair_result": res},
            )

        elif cat in ("episode_retention_exceeded", "orphan_events_dir"):
            # Action: episode_prune / dir_prune
            if dry_run:
                return GcResult(
                    success=True,
                    dry_run=True,
                    action="episode_prune" if cat == "episode_retention_exceeded" else "events_prune",
                    target_path=target_path_str,
                    details={"status": "dry_run_skipped_delete"},
                )

            if target_full_path.exists():
                if target_full_path.is_dir():
                    shutil.rmtree(target_full_path)
                else:
                    target_full_path.unlink()

            return GcResult(
                success=True,
                dry_run=False,
                action="episode_prune" if cat == "episode_retention_exceeded" else "events_prune",
                target_path=target_path_str,
                details={"deleted": str(target_full_path)},
            )

        else:
            raise GcWhitelistError(f"No repair handler defined for category '{cat}'")
