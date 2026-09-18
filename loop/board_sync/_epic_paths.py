from __future__ import annotations

from pathlib import Path

from harness.hooks.epic_paths import (
    epic_id_from_plan_path,
    find_decompose_index_path,
    find_plan_md_path,
)


def plan_path(project: Path, role: str, epic_id: str) -> Path | None:
    return find_plan_md_path(project, role, epic_id)


__all__ = [
    "epic_id_from_plan_path",
    "find_decompose_index_path",
    "plan_path",
]
