"""Formula render helper library for generating decompose directory draft from formula."""

from __future__ import annotations

import sys
from pathlib import Path
import yaml

from loop.schemas.formula import load_formula, DecomposeFormula, FormulaStep

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / ".cursor" / "templates" / "decompose"
FORMULAS_DIR = ROOT / "loop" / "formulas"


def find_formula_file(formula_id: str, custom_dir: Path | None = None) -> Path:
    """Find formula YAML file by id in FORMULAS_DIR or custom_dir."""
    search_dir = custom_dir or FORMULAS_DIR
    p = Path(formula_id)
    if p.is_file():
        return p
    for ext in (".yaml", ".yml"):
        candidate = search_dir / f"{formula_id}{ext}"
        if candidate.is_file():
            return candidate
    if search_dir.is_dir():
        for f in search_dir.glob("*.y*ml"):
            try:
                content = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(content, dict) and content.get("id") == formula_id:
                    return f
            except Exception:
                pass
    raise ValueError(f"Formula '{formula_id}' not found in {search_dir}")


def render_step(
    formula_step: FormulaStep,
    step_idx: int,
    epic_id: str,
    slug: str,
    base_template_path: Path | None = None,
) -> dict:
    """Render a single step dictionary merged with base template."""
    tmpl_path = base_template_path or (TEMPLATES_DIR / "epic-step.yaml")
    if tmpl_path.exists():
        with open(tmpl_path, "r", encoding="utf-8") as f:
            base_data = yaml.safe_load(f) or {}
    else:
        base_data = {}

    plan_id = f"{epic_id}-{slug}" if (epic_id and slug and slug not in epic_id) else (epic_id or slug)
    step_id = f"s{step_idx:02d}"

    goal_template = formula_step.goal_template
    try:
        goal = goal_template.format(
            epic_name=plan_id,
            epic_id=epic_id,
            slug=slug,
            plan_id=plan_id,
        )
    except (KeyError, IndexError, ValueError):
        goal = goal_template

    res = dict(base_data)
    res["schema"] = "epic-decompose/v1"
    res["role"] = "back"
    res["step_id"] = step_id
    res["plan_id"] = plan_id
    res["title"] = formula_step.title
    res["next_phase"] = "BACK IMPLEMENT"
    res["needs_creative"] = "no"
    res["goal"] = goal
    res["plan_contract"] = {
        "fr_ids": [f"FR-{step_idx:03d}"],
        "nouns": [formula_step.title],
        "layout_paths": [f.format(epic_name=plan_id, epic_id=epic_id, slug=slug) if "{" in f else f for f in formula_step.typical_files_pattern],
        "ac_quotes": [f"Verify {formula_step.title}"],
        "plan_jumps": [f"plan-{plan_id}.md:1-50"],
    }

    if "context" not in res or not isinstance(res["context"], dict):
        res["context"] = {"consumes": [], "produces": [], "plan_refs": [], "files": []}

    files = [
        f.format(epic_name=plan_id, epic_id=epic_id, slug=slug) if "{" in f else f
        for f in formula_step.typical_files_pattern
    ]
    res["context"]["files"] = files

    checkpoints = []
    for idx, hint in enumerate(formula_step.verify_hints, start=1):
        try:
            v_str = hint.format(epic_name=plan_id, epic_id=epic_id, slug=slug)
        except Exception:
            v_str = hint
        checkpoints.append(
            {
                "id": f"cp{idx}",
                "criterion": f"Verify {formula_step.title} requirement",
                "verify": v_str,
            }
        )
    if not checkpoints:
        checkpoints.append(
            {
                "id": "cp1",
                "criterion": f"Verify {formula_step.title} implementation",
                "verify": ".venv/bin/pytest -q",
            }
        )
    res["checkpoints"] = checkpoints
    res.setdefault("as_built", [])
    res.setdefault("delta", [f"Implement {formula_step.title} for {plan_id}"])
    res.setdefault("deletes", [])
    res.setdefault("out_of_scope", [])
    res.setdefault("skills", {"code_surface": "api", "impl": []})
    res.setdefault("verify", [])
    res.setdefault("tdd", [])

    return res


def _get_formula_steps(formula_id: str, custom_formulas_dir: Path | None = None) -> list[FormulaStep]:
    """Retrieve formula steps by formula_id."""
    formula_path = find_formula_file(formula_id, custom_formulas_dir)
    formula = load_formula(formula_path)
    return formula.steps


def render_formula(
    formula_id: str,
    epic_id: str,
    slug: str,
    out_dir: str | Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    custom_formulas_dir: Path | None = None,
    role: str = "back",
    project_root: Path | None = None,
) -> list[str]:
    """Render full formula into index.yaml + step shards.

    Returns list of paths formatted or written.
    Raises ValueError if formula not found, file overwrite attempted without force, etc.
    """
    formula_path = find_formula_file(formula_id, custom_formulas_dir)
    formula = load_formula(formula_path)

    plan_id = f"{epic_id}-{slug}" if (epic_id and slug and slug not in epic_id) else (epic_id or slug)

    index_data = {
        "schema": "epic-decompose-index/v1",
        "plan_id": plan_id,
        "source_md": "index.md",
        "status_canon": "index.yaml",
        "steps": [],
    }

    step_files_content: list[tuple[str, str, str, dict]] = []
    for idx, f_step in enumerate(formula.steps, start=1):
        step_id = f"s{idx:02d}"
        title_slug = f_step.title.lower().replace(" ", "-")
        filename = f"{step_id}-{title_slug}.yaml"
        step_dict = render_step(f_step, idx, epic_id, slug)
        step_files_content.append((step_id, title_slug, filename, step_dict))

        index_data["steps"].append(
            {
                "id": step_id,
                "file": filename,
                "title": f_step.title,
                "next_phase": "BACK IMPLEMENT",
                "status": "pending",
            }
        )

    written_paths: list[str] = []

    if dry_run:
        out_str = f"# --- index.yaml ---\n{yaml.safe_dump(index_data, sort_keys=False)}\n"
        for _, _, filename, step_dict in step_files_content:
            out_str += f"# --- {filename} ---\n{yaml.safe_dump(step_dict, sort_keys=False)}\n"
        print(out_str, end="")
        return ["index.yaml"] + [fn for _, _, fn, _ in step_files_content]

    if out_dir:
        target_dir = Path(out_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        index_path = target_dir / "index.yaml"
        target_step_paths = [(target_dir / filename, step_dict) for _, _, filename, step_dict in step_files_content]
    else:
        from loop.paths.epic_layout import resolve, EpicLayoutKind

        index_path = resolve(
            role=role,
            epic_id=epic_id,
            kind=EpicLayoutKind.DECOMPOSE_INDEX_YAML,
            project_root=project_root,
        )
        target_step_paths = [
            (
                resolve(
                    role=role,
                    epic_id=epic_id,
                    kind=EpicLayoutKind.DECOMPOSE_STEP,
                    step_id=step_id,
                    step_slug=title_slug,
                    project_root=project_root,
                ),
                step_dict,
            )
            for step_id, title_slug, _, step_dict in step_files_content
        ]

    if index_path.exists() and not force:
        raise ValueError(f"File {index_path} already exists. Use --force to overwrite.")

    for p, _ in target_step_paths:
        if p.exists() and not force:
            raise ValueError(f"File {p} already exists. Use --force to overwrite.")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(index_data, f, sort_keys=False)
    written_paths.append(str(index_path))

    for p, step_dict in target_step_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(step_dict, f, sort_keys=False)
        written_paths.append(str(p))

    return written_paths


def list_formulas(formulas_dir: Path | None = None) -> list[DecomposeFormula]:
    """Glob loop/formulas/*.yaml, load each formula, return list sorted by formula.id."""
    search_dir = formulas_dir or FORMULAS_DIR
    res: list[DecomposeFormula] = []
    if not search_dir.is_dir():
        return res
    for f in search_dir.glob("*.y*ml"):
        formula = load_formula(f)
        res.append(formula)
    return sorted(res, key=lambda f: f.id)

