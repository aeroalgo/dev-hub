"""Scope enforcement for incident auto-pilot sessions."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loop.incidents.schema import IncidentRecord


def build_allowlist(incident: IncidentRecord, project_root: Path) -> list[str]:
    """Build canonical allowed absolute paths for an incident session."""
    root = project_root.resolve()
    epic_id = incident.epic_id
    step_id = incident.step_id
    incident_id = incident.incident_id

    from loop.paths.epic_layout import resolve, EpicLayoutKind

    plan_dir = root / "memory-bank" / "back" / "plan" / epic_id
    impl_dir = root / "memory-bank" / "back" / "implement" / epic_id

    allowed = [
        str((root / "memory-bank" / "activeContext.md").resolve()),
        str((root / "runtime" / incident_id / "epic").resolve()),
    ]

    plan_step = resolve(role="back", epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_STEP, step_id=step_id, project_root=root)
    impl_step = resolve(role="back", epic_id=epic_id, kind=EpicLayoutKind.IMPLEMENT_STEP, step_id=step_id, project_root=root)

    allowed.append(str(plan_step.resolve()))
    allowed.append(str(impl_step.resolve()))

    return allowed


def check_path_allowed(path: str | Path, allowlist: list[str]) -> bool:
    """Check if normalized absolute target path is allowed (exact or directory prefix match)."""
    try:
        target = Path(path).resolve()
    except (ValueError, RuntimeError, OSError):
        return False

    target_str = str(target)

    for item in allowlist:
        try:
            allowed_path = Path(item).resolve()
        except (ValueError, RuntimeError, OSError):
            continue

        allowed_str = str(allowed_path)
        if target_str == allowed_str:
            return True

        # Check directory prefix match
        # To avoid prefix trickery like /path/foo matching /path/foobar, ensure trailing separator or is_relative_to
        try:
            if target.is_relative_to(allowed_path):
                return True
        except AttributeError:  # Python < 3.9 compatibility if any, though python 3.12 is guaranteed
            if target_str.startswith(allowed_str + os.sep):
                return True

    return False


def write_scope_file(allowlist: list[str], scope_path: Path) -> None:
    """Serialize allowlist to JSON file for pretool guard consumption."""
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    with scope_path.open("w", encoding="utf-8") as f:
        json.dump({"allowlist": allowlist}, f, indent=2, ensure_ascii=False)
