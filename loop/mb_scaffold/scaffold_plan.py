"""Scaffold for epic plan artifacts (layout v2)."""

from pathlib import Path
from typing import Optional, Union

from loop.mb_scaffold.models import ScaffoldResult
from loop.paths.epic_layout import resolve, EpicLayoutKind


def scaffold_plan(
    epic_id: str,
    role: str = "back",
    title: Optional[str] = None,
    level: str = "epic",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold plan/<epic_id>/md/plan.md only."""
    created = []
    skipped = []
    _ = level

    plan_md_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_MD, project_root=project_root)

    if plan_md_path.exists() and not force:
        raise ValueError(f"Plan file already exists: {plan_md_path}. Use force=True to overwrite.")

    md_content = f"""# Plan: {title or epic_id}

## Goal

## Context

## Requirements

## Stages

## Technology Axiom
"""

    rel = str(plan_md_path)
    if dry_run:
        created.append(rel)
    else:
        plan_md_path.parent.mkdir(parents=True, exist_ok=True)
        plan_md_path.write_text(md_content, encoding="utf-8")
        created.append(rel)

    return ScaffoldResult(ok=True, created=created, skipped=skipped, dry_run=dry_run)
