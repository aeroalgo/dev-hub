"""Scaffold for epic decompose artifacts (layout v2)."""

import os
from pathlib import Path
from typing import List, Optional, Union
import yaml

from loop.mb_scaffold.models import ScaffoldResult
from loop.paths.epic_layout import resolve, EpicLayoutKind
from loop.schemas.plan_spec import PlanSpec, PlanSummary, OutlineStep


def _check_step_overwrite(path: Path, force: bool) -> None:
    if not path.exists():
        return
    if force:
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            goal = data.get("goal", "")
            # If goal is non-empty and not empty placeholder, fail
            if goal and str(goal).strip() != "":
                raise ValueError(f"Step file {path} has non-empty goal. Use force=True to overwrite.")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        # If unparseable but exists
        raise ValueError(f"Step file {path} already exists. Use force=True to overwrite.")


def scaffold_decompose(
    epic_id: str,
    role: str = "back",
    plan_spec: Optional[PlanSpec] = None,
    formula_id: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    project_root: Optional[Union[str, Path]] = None,
) -> ScaffoldResult:
    """Scaffold decompose steps (sNN skeleton) and decompose-index from plan.yaml or PlanSpec."""
    created = []
    skipped = []

    formula = None
    if formula_id:
        from loop.formula_render import find_formula_file, _get_formula_steps
        from loop.schemas.formula import load_formula
        formula_file = find_formula_file(formula_id)
        formula = load_formula(formula_file)

    if plan_spec is None:
        plan_yaml_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_YAML, project_root=project_root)
        if plan_yaml_path.exists():
            raw = yaml.safe_load(plan_yaml_path.read_text(encoding="utf-8"))
            plan_spec = PlanSpec.model_validate(raw)
        elif formula is not None:
            formula_steps = []
            for idx, f_step in enumerate(formula.steps, start=1):
                formula_steps.append(
                    OutlineStep(
                        step_id=f"s{idx:02d}",
                        title=f_step.title,
                        maps_to=[f"FR-{idx:03d}"],
                    )
                )
            plan_spec = PlanSpec(
                plan_id=epic_id,
                level="epic",
                title=epic_id,
                summary=PlanSummary(step_count_floor=len(formula_steps), requirement_count=len(formula_steps)),
                requirements=[],
                outline_steps=formula_steps,
            )
        else:
            raise FileNotFoundError(f"plan.yaml not found at {plan_yaml_path}")

    if formula is not None and plan_spec is not None:
        existing_steps = list(plan_spec.outline_steps or [])
        formula_steps_by_fr = {f"FR-{i:03d}": f_step for i, f_step in enumerate(formula.steps, start=1)}
        formula_steps_by_id = {f"s{i:02d}": f_step for i, f_step in enumerate(formula.steps, start=1)}
        for idx, step in enumerate(existing_steps):
            f_step = None
            for fr in (step.maps_to or []):
                if fr in formula_steps_by_fr:
                    f_step = formula_steps_by_fr[fr]
                    break
            if f_step is None:
                f_step = formula_steps_by_id.get(step.step_id)
            if f_step is None and idx < len(formula.steps):
                f_step = formula.steps[idx]

            if f_step:
                step.title = f_step.title

        existing_count = len(existing_steps)
        if existing_count < len(formula.steps):
            for idx in range(existing_count, len(formula.steps)):
                f_step = formula.steps[idx]
                s_num = idx + 1
                existing_steps.append(
                    OutlineStep(
                        step_id=f"s{s_num:02d}",
                        title=f_step.title,
                        maps_to=[f"FR-{s_num:03d}"],
                    )
                )
        plan_spec.outline_steps = existing_steps

    outline_steps: List[OutlineStep] = plan_spec.outline_steps or []

    # Check overwrite for index and steps
    index_md_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=project_root)
    index_yaml_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=project_root)

    step_files_to_write = []
    index_steps = []

    for step in outline_steps:
        s_id = step.step_id
        # slug from title or step_id
        slug = step.title.lower().replace(" ", "-").replace("/", "-") if step.title else ""
        step_path = resolve(
            role=role,
            epic_id=epic_id,
            kind=EpicLayoutKind.DECOMPOSE_STEP,
            step_id=s_id,
            step_slug=slug or None,
            project_root=project_root,
        )
        _check_step_overwrite(step_path, force)

        step_filename = step_path.name
        index_steps.append({
            "id": s_id,
            "file": step_filename,
            "title": step.title,
            "next_phase": f"{role.upper()} IMPLEMENT",
            "status": "pending",
        })

        step_skeleton = {
            "schema": "epic-decompose/v1",
            "role": role,
            "step_id": s_id,
            "plan_id": epic_id,
            "title": step.title,
            "next_phase": f"{role.upper()} IMPLEMENT",
            "needs_creative": "no",
            "goal": "",
            "plan_contract": {
                "fr_ids": step.maps_to or [],
                "nouns": [],
                "layout_paths": [],
                "ac_quotes": [],
                "plan_jumps": [],
            },
            "context": {
                "consumes": [],
                "produces": [],
                "plan_refs": step.maps_to or [],
                "files": [],
            },
            "as_built": [],
            "delta": [],
            "deletes": [],
            "out_of_scope": [],
            "skills": {
                "code_surface": "api",
                "impl": ["modern-python", "python-testing-patterns"],
            },
            "checkpoints": [],
            "verify": [],
            "tdd": [],
        }
        step_yaml_content = yaml.dump(step_skeleton, sort_keys=False)
        step_files_to_write.append((step_path, step_yaml_content))

    # Decompose index YAML
    index_yaml_data = {
        "schema": "epic-decompose-index/v1",
        "plan_id": epic_id,
        "source_md": "decompose-index.md",
        "status_canon": "decompose-index.yaml",
        "steps": index_steps,
    }
    index_yaml_content = yaml.dump(index_yaml_data, sort_keys=False)

    # Decompose index MD
    # Coverage rows for requirements
    req_rows = ""
    for req in plan_spec.requirements:
        req_rows += f"| {req.id} | {req.text} | | pending |\n"

    index_md_content = f"""# Decompose: {plan_spec.title or epic_id}

## Steps

## Requirements coverage
| Requirement | Description | Step | Status |
|---|---|---|---|
{req_rows}
## Stages coverage

## Outcome map

## Replacement cleanup
"""

    # Check index overwrite
    if (index_md_path.exists() or index_yaml_path.exists()) and not force:
        # Check if already exists
        if index_md_path.exists():
            _check_step_overwrite(index_md_path, force)
        if index_yaml_path.exists():
            _check_step_overwrite(index_yaml_path, force)

    all_to_write = [(index_md_path, index_md_content), (index_yaml_path, index_yaml_content)] + step_files_to_write

    for path, content in all_to_write:
        rel = str(path)
        if dry_run:
            created.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(rel)

    return ScaffoldResult(ok=True, created=created, skipped=skipped, dry_run=dry_run)
