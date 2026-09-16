from __future__ import annotations

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic_paths import (  # noqa: E402
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
