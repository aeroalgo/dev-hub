"""Scaffold for epic plan artifacts (layout v2)."""

import os
from pathlib import Path
from typing import Optional, Union
import yaml

from loop.mb_scaffold.models import ScaffoldRequest, ScaffoldResult
from loop.paths.epic_layout import resolve, EpicLayoutKind
from loop.schemas.plan_spec import PlanSpec, PlanSummary


def _check_overwrite(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise ValueError(f"Target file already exists: {path}. Use force=True to overwrite.")


def scaffold_plan(
    epic_id: str,
    role: str = "back",
    title: Optional[str] = None,
    level: str = "epic",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold plan/<epic_id>/md/plan.md and yaml/plan.yaml."""
    created = []
    skipped = []

    plan_md_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_MD, project_root=project_root)
    plan_yaml_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_YAML, project_root=project_root)

    # Overwrite check
    for p in [plan_md_path, plan_yaml_path]:
        if p.exists() and not force:
            raise ValueError(f"Plan file already exists: {p}. Use force=True to overwrite.")

    md_content = f"""# Plan: {title or epic_id}

## Goal

## Context

## Requirements

## Stages

## Technology Axiom
"""
    spec = PlanSpec(
        schema="epic-plan/v1",
        plan_id=epic_id,
        level=level,
        title=title or epic_id,
        summary=PlanSummary(step_count_floor=0, requirement_count=0),
        requirements=[],
        outline_steps=[],
        stages=[],
        sunset_refs=[],
    )
    yaml_content = yaml.dump(spec.model_dump(by_alias=True, exclude_none=True), sort_keys=False)

    for path, content in [(plan_md_path, md_content), (plan_yaml_path, yaml_content)]:
        rel = str(path)
        if dry_run:
            created.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(rel)

    return ScaffoldResult(ok=True, created=created, skipped=skipped, dry_run=dry_run)
