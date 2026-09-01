"""Detector for orphan implement yaml files without matching plan."""

from __future__ import annotations

from pathlib import Path
from loop.janitor.schema import JanitorFinding


def detect_orphan_implement_yaml(cwd: Path) -> list[JanitorFinding]:
    """Scan memory-bank/*/implement/ for yaml files without corresponding plan."""
    findings: list[JanitorFinding] = []
    mb = cwd / "memory-bank"
    if not mb.is_dir():
        return findings

    for role_dir in mb.iterdir():
        if not role_dir.is_dir():
            continue
        impl_dir = role_dir / "implement"
        if not impl_dir.is_dir():
            continue
        plan_dir = role_dir / "plan"

        for epic_impl_dir in impl_dir.iterdir():
            if not epic_impl_dir.is_dir():
                continue
            epic_folder_name = epic_impl_dir.name
            if epic_folder_name.startswith("implement-"):
                epic_id = epic_folder_name[len("implement-") :]
            else:
                epic_id = epic_folder_name

            matching_plan_folder = plan_dir / f"decompose-{epic_id}"
            has_matching_plan = (
                matching_plan_folder.is_dir()
                or any(plan_dir.glob(f"*{epic_id}*"))
                if plan_dir.is_dir()
                else False
            )

            if not has_matching_plan:
                rel_path = epic_impl_dir.relative_to(cwd)
                findings.append(
                    JanitorFinding(
                        category="orphan_implement_yaml",
                        description=f"Implement directory '{epic_impl_dir.name}' has no matching plan in '{plan_dir}'",
                        target_path=str(rel_path),
                        actionable=True,
                        metadata={
                            "epic_id": epic_id,
                            "implement_dir": str(rel_path),
                        },
                    )
                )

    return findings
