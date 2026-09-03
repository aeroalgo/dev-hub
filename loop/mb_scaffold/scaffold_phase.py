"""Scaffold for QA, Analyze, Audit artifacts (layout v2)."""

import os
from pathlib import Path
from typing import Optional, Union
import yaml

from loop.mb_scaffold.models import ScaffoldResult
from loop.paths.epic_layout import resolve, EpicLayoutKind


def _check_overwrite(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if force:
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            status = data.get("status") or data.get("verdict")
            if status:
                raise ValueError(f"Artifact {path} already has status/verdict. Use force=True to overwrite.")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Artifact {path} already exists. Use force=True to overwrite.")


def scaffold_qa(
    epic_id: str,
    role: str = "back",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold qa/<epic_id>/yaml/qa.yaml."""
    path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.QA_YAML, project_root=project_root)
    _check_overwrite(path, force)

    content = {
        "schema": "epic-qa/v1",
        "role": role,
        "plan_id": epic_id,
        "verdict": "pending",
        "summary": "",
        "suites": [],
        "findings": [],
        "evidence": [],
    }
    yaml_content = yaml.dump(content, sort_keys=False)
    created = [str(path)]
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_content, encoding="utf-8")

    return ScaffoldResult(ok=True, created=created, skipped=[], dry_run=dry_run)


def scaffold_analyze(
    epic_id: str,
    role: str = "back",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold analyze/<epic_id>/yaml/analyze.yaml."""
    path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.ANALYZE_YAML, project_root=project_root)
    _check_overwrite(path, force)

    content = {
        "schema": "epic-analyze/v1",
        "role": role,
        "plan_id": epic_id,
        "verdict": "pending",
        "summary": "",
        "findings": [],
        "coverage_check": {},
    }
    yaml_content = yaml.dump(content, sort_keys=False)
    created = [str(path)]
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_content, encoding="utf-8")

    return ScaffoldResult(ok=True, created=created, skipped=[], dry_run=dry_run)


def scaffold_audit(
    epic_id: str,
    role: str = "back",
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold audit/<epic_id>/yaml/audit.yaml."""
    path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.AUDIT_YAML, project_root=project_root)
    _check_overwrite(path, force)

    content = {
        "schema": "epic-audit/v1",
        "role": role,
        "plan_id": epic_id,
        "verdict": "pending",
        "summary": "",
        "gaps": [],
        "recommendations": [],
    }
    yaml_content = yaml.dump(content, sort_keys=False)
    created = [str(path)]
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_content, encoding="utf-8")

    return ScaffoldResult(ok=True, created=created, skipped=[], dry_run=dry_run)
