"""Scaffold for epic implement artifacts (layout v2)."""

import os
from pathlib import Path
from typing import List, Optional, Union
import yaml

from loop.mb_scaffold.models import ScaffoldResult
from loop.paths.epic_layout import resolve, EpicLayoutKind


def _check_step_overwrite(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if force:
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            status = data.get("status", "")
            if status == "completed":
                raise ValueError(f"Implement step file {path} is already completed. Use force=True to overwrite.")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Implement step file {path} already exists. Use force=True to overwrite.")


def scaffold_implement(
    epic_id: str,
    step_id: str,
    step_slug: Optional[str] = None,
    role: str = "back",
    title: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold a single implement step."""
    created = []
    skipped = []

    step_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.IMPLEMENT_STEP,
        step_id=step_id,
        step_slug=step_slug,
        project_root=project_root,
    )
    _check_step_overwrite(step_path, force)

    step_content = {
        "schema": "epic-implement/v1",
        "role": role,
        "step_id": step_id,
        "plan_id": epic_id,
        "title": title or f"{step_id} implementation",
        "status": "in_progress",
        "skills_used": [],
        "discovery": [],
        "gaps": {"status": "none"},
        "done": [],
        "files": [],
        "deletes": [],
        "tests": [],
        "integration_check": [],
        "grep_control": [],
        "verification_results": [],
        "checkpoints": [],
    }

    yaml_content = yaml.dump(step_content, sort_keys=False)
    rel = str(step_path)
    if dry_run:
        created.append(rel)
    else:
        step_path.parent.mkdir(parents=True, exist_ok=True)
        step_path.write_text(yaml_content, encoding="utf-8")
        created.append(rel)

    return ScaffoldResult(ok=True, created=created, skipped=skipped, dry_run=dry_run)


def scaffold_implement_all(
    epic_id: str,
    role: str = "back",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold all implement steps from decompose-index.yaml."""
    created = []
    skipped = []

    index_yaml_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_INDEX_YAML,
        project_root=project_root,
    )
    if not index_yaml_path.exists():
        raise FileNotFoundError(f"decompose-index.yaml not found at {index_yaml_path}")

    index_data = yaml.safe_load(index_yaml_path.read_text(encoding="utf-8"))
    steps = index_data.get("steps", [])

    for step_info in steps:
        s_id = step_info.get("id")
        file_name = step_info.get("file", "")
        title = step_info.get("title", "")
        # extract slug from filename e.g. s01-foo.yaml -> foo
        s_slug = None
        if file_name.endswith(".yaml"):
            base = file_name[:-5]
            if "-" in base:
                parts = base.split("-", 1)
                s_slug = parts[1]

        res = scaffold_implement(
            epic_id=epic_id,
            step_id=s_id,
            step_slug=s_slug,
            role=role,
            title=title,
            force=force,
            dry_run=dry_run,
            project_root=project_root,
        )
        created.extend(res.created)
        skipped.extend(res.skipped)

    return ScaffoldResult(ok=True, created=created, skipped=skipped, dry_run=dry_run)
