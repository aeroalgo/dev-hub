"""Migrate memory-bank from flat v1 layout to v2 layout.

Flat v1 layout:
  memory-bank/{role}/plan/plan-{epic_id}.md
  memory-bank/{role}/plan/decompose-{epic_id}/index.md
  memory-bank/{role}/plan/decompose-{epic_id}/index.yaml
  memory-bank/{role}/plan/decompose-{epic_id}/sNN-*.yaml
  memory-bank/{role}/implement/implement-{epic_id}/sNN-*.yaml
  memory-bank/{role}/qa/qa-{epic_id}.yaml
  memory-bank/{role}/analyze/analyze-{epic_id}.yaml
  memory-bank/{role}/audit/audit-{epic_id}.yaml

Layout v2:
  memory-bank/{role}/plan/{epic_id}/md/plan.md
  memory-bank/{role}/plan/{epic_id}/yaml/plan.yaml
  memory-bank/{role}/plan/{epic_id}/md/decompose-index.md
  memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml
  memory-bank/{role}/plan/{epic_id}/yaml/steps/sNN-*.yaml
  memory-bank/{role}/implement/{epic_id}/yaml/steps/sNN-*.yaml
  memory-bank/{role}/qa/{epic_id}/yaml/qa.yaml
  memory-bank/{role}/analyze/{epic_id}/yaml/analyze.yaml
  memory-bank/{role}/audit/{epic_id}/yaml/audit.yaml
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import yaml

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from loop.paths.epic_layout import resolve, EpicLayoutKind


def get_project_root(cwd: Optional[Union[str, Path]] = None) -> Path:
    if cwd is not None:
        return Path(cwd)
    root = os.environ.get("PROJECT_ROOT")
    if root:
        return Path(root)
    return Path.cwd()


def discover_v1_epics(cwd: Optional[Union[str, Path]] = None) -> List[Tuple[str, str]]:
    """Discover epics in v1 flat layout across all memory-bank roles.

    Returns list of (role, epic_id) sorted by role, epic_id.
    """
    root = get_project_root(cwd)
    mb = root / "memory-bank"
    if not mb.exists():
        return []

    epics_found: Set[Tuple[str, str]] = set()

    for role_dir in mb.iterdir():
        if not role_dir.is_dir():
            continue
        role = role_dir.name
        plan_dir = role_dir / "plan"
        if not plan_dir.exists() or not plan_dir.is_dir():
            continue

        for p in plan_dir.glob("plan-*.md"):
            if p.is_file():
                epic_id = p.stem[len("plan-") :]
                if epic_id:
                    epics_found.add((role, epic_id))

        for p in plan_dir.glob("decompose-*"):
            if p.is_dir():
                epic_id = p.name[len("decompose-") :]
                if epic_id:
                    epics_found.add((role, epic_id))

    return sorted(list(epics_found))


def is_migrated(epic_id: str, role: str = "back", cwd: Optional[Union[str, Path]] = None) -> bool:
    """Check if epic is already migrated to v2 layout.

    An epic is considered migrated if its v2 plan directory exists and v1 plan artifacts are absent.
    """
    root = get_project_root(cwd)
    v2_plan_dir = root / "memory-bank" / role / "plan" / epic_id
    v1_plan_md = root / "memory-bank" / role / "plan" / f"plan-{epic_id}.md"
    v1_decomp_dir = root / "memory-bank" / role / "plan" / f"decompose-{epic_id}"

    # If v1 artifacts do not exist and v2 exists, it's migrated
    if v2_plan_dir.exists() and not v1_plan_md.exists() and not v1_decomp_dir.exists():
        return True
    return False


def update_refs(file_path: Path, old_refs: List[Tuple[str, str]], dry_run: bool = False) -> bool:
    """Update reference patterns in a text/yaml/md file."""
    if not file_path.exists() or not file_path.is_file():
        return False
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    updated_content = content
    for old_pattern, new_pattern in old_refs:
        updated_content = updated_content.replace(old_pattern, new_pattern)

    if updated_content != content:
        if not dry_run:
            file_path.write_text(updated_content, encoding="utf-8")
        return True
    return False


def check_active_implement(epic_id: str, role: str = "back", cwd: Optional[Union[str, Path]] = None) -> bool:
    """Check if the epic has steps in_progress in decompose index.yaml."""
    root = get_project_root(cwd)
    decomp_yaml = root / "memory-bank" / role / "plan" / f"decompose-{epic_id}" / "index.yaml"
    if not decomp_yaml.exists():
        decomp_yaml = root / "memory-bank" / role / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    if not decomp_yaml.exists():
        return False

    try:
        data = yaml.safe_load(decomp_yaml.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            steps = data.get("steps", [])
            for step in steps:
                if isinstance(step, dict) and step.get("status") == "in_progress":
                    return True
    except Exception:
        pass
    return False


def migrate_epic(
    epic_id: str,
    role: str = "back",
    cwd: Optional[Union[str, Path]] = None,
    dry_run: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """Migrate a single epic from v1 to v2 layout.

    Returns migration result dict:
      {
        "epic_id": epic_id,
        "role": role,
        "status": "migrated" | "skipped" | "dry_run",
        "moved": [{"from": ..., "to": ...}],
        "refs_updated": [...],
        "warning": Optional[str]
      }
    """
    root = get_project_root(cwd)
    base = root / "memory-bank" / role

    if is_migrated(epic_id, role, cwd):
        return {
            "epic_id": epic_id,
            "role": role,
            "status": "skipped",
            "moved": [],
            "refs_updated": [],
            "warning": "Already migrated",
        }

    # Active IMPLEMENT guard
    has_active = check_active_implement(epic_id, role, cwd)
    if has_active and not force:
        raise RuntimeError(
            f"Active IMPLEMENT guard: epic {role}/{epic_id} has steps in_progress. Use --force to migrate."
        )

    planned_moves: List[Tuple[Path, Path]] = []
    cleanup_dirs: List[Path] = []

    # 1. Plan md
    v1_plan_md = base / "plan" / f"plan-{epic_id}.md"
    v2_plan_md = base / "plan" / epic_id / "md" / "plan.md"
    if v1_plan_md.exists():
        planned_moves.append((v1_plan_md, v2_plan_md))

    # 2. Decompose dir
    v1_decomp_dir = base / "plan" / f"decompose-{epic_id}"
    if v1_decomp_dir.exists() and v1_decomp_dir.is_dir():
        v2_decomp_md = base / "plan" / epic_id / "md" / "decompose-index.md"
        v2_decomp_yaml = base / "plan" / epic_id / "yaml" / "decompose-index.yaml"
        v2_steps_dir = base / "plan" / epic_id / "yaml" / "steps"

        for child in v1_decomp_dir.iterdir():
            if child.name in ("index.md", "decompose-index.md"):
                planned_moves.append((child, v2_decomp_md))
            elif child.name in ("index.yaml", "decompose-index.yaml"):
                planned_moves.append((child, v2_decomp_yaml))
            elif child.is_file():
                planned_moves.append((child, v2_steps_dir / child.name))
        cleanup_dirs.append(v1_decomp_dir)

    # 3. Implement dir
    v1_impl_dir = base / "implement" / f"implement-{epic_id}"
    if v1_impl_dir.exists() and v1_impl_dir.is_dir():
        v2_impl_steps_dir = base / "implement" / epic_id / "yaml" / "steps"
        for child in v1_impl_dir.iterdir():
            if child.is_file():
                planned_moves.append((child, v2_impl_steps_dir / child.name))
        cleanup_dirs.append(v1_impl_dir)

    # 4. QA yaml
    v1_qa_yaml = base / "qa" / f"qa-{epic_id}.yaml"
    v2_qa_yaml = base / "qa" / epic_id / "yaml" / "qa.yaml"
    if v1_qa_yaml.exists():
        planned_moves.append((v1_qa_yaml, v2_qa_yaml))

    # 5. Analyze yaml
    v1_analyze_yaml = base / "analyze" / f"analyze-{epic_id}.yaml"
    v2_analyze_yaml = base / "analyze" / epic_id / "yaml" / "analyze.yaml"
    if v1_analyze_yaml.exists():
        planned_moves.append((v1_analyze_yaml, v2_analyze_yaml))

    # 6. Audit yaml
    v1_audit_yaml = base / "audit" / f"audit-{epic_id}.yaml"
    v2_audit_yaml = base / "audit" / epic_id / "yaml" / "audit.yaml"
    if v1_audit_yaml.exists():
        planned_moves.append((v1_audit_yaml, v2_audit_yaml))

    moved_records: List[Dict[str, str]] = []
    for src, dst in planned_moves:
        moved_records.append({"from": str(src.relative_to(root)), "to": str(dst.relative_to(root))})

    refs_updated_records: List[str] = []

    # Ref patterns to replace
    ref_replacements = [
        (f"plan-{epic_id}.md", f"plan/{epic_id}/md/plan.md"),
        (f"decompose-{epic_id}/index.md", f"{epic_id}/md/decompose-index.md"),
        (f"decompose-{epic_id}/index.yaml", f"{epic_id}/yaml/decompose-index.yaml"),
        (f"decompose-{epic_id}/", f"{epic_id}/yaml/steps/"),
        (f"implement-{epic_id}/", f"{epic_id}/yaml/steps/"),
    ]

    if not dry_run:
        # Perform moves
        for src, dst in planned_moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

        # Cleanup empty v1 dirs
        for d in cleanup_dirs:
            if d.exists():
                try:
                    # remove if empty, or rm tree
                    shutil.rmtree(str(d))
                except Exception:
                    pass

        # Update refs in migrated files
        all_migrated_files: List[Path] = [dst for _, dst in planned_moves]
        for f in all_migrated_files:
            if f.exists() and f.is_file():
                if update_refs(f, ref_replacements, dry_run=False):
                    refs_updated_records.append(str(f.relative_to(root)))

    return {
        "epic_id": epic_id,
        "role": role,
        "status": "dry_run" if dry_run else "migrated",
        "moved": moved_records,
        "refs_updated": refs_updated_records,
        "warning": "in_progress steps forced" if (has_active and force) else None,
    }


def migrate_all(
    cwd: Optional[Union[str, Path]] = None,
    dry_run: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """Migrate all discovered v1 epics to v2 layout."""
    epics = discover_v1_epics(cwd)
    results = []
    errors = []

    for role, epic_id in epics:
        try:
            res = migrate_epic(epic_id=epic_id, role=role, cwd=cwd, dry_run=dry_run, force=force)
            results.append(res)
        except Exception as e:
            errors.append({"epic_id": epic_id, "role": role, "error": str(e)})

    return {
        "ok": len(errors) == 0,
        "dry_run": dry_run,
        "total_discovered": len(epics),
        "results": results,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate memory-bank from flat v1 layout to v2 layout.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", default=True, help="Preview migration plan (default)")
    mode_group.add_argument("--apply", action="store_true", help="Apply migration changes")
    parser.add_argument("--epic", type=str, default=None, help="Specific epic_id to migrate")
    parser.add_argument("--role", type=str, default="back", help="Role for specific epic")
    parser.add_argument("--force", action="store_true", help="Force migration even if steps are in_progress")
    parser.add_argument("--cwd", type=str, default=None, help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()
    is_apply = args.apply
    dry_run = not is_apply

    if args.epic:
        try:
            res = migrate_epic(epic_id=args.epic, role=args.role, cwd=args.cwd, dry_run=dry_run, force=args.force)
            out = {"ok": True, "dry_run": dry_run, "results": [res], "errors": []}
        except Exception as e:
            out = {"ok": False, "dry_run": dry_run, "results": [], "errors": [{"epic_id": args.epic, "error": str(e)}]}
    else:
        out = migrate_all(cwd=args.cwd, dry_run=dry_run, force=args.force)

    if args.json or not sys.stdout.isatty():
        print(json.dumps(out, indent=2))
    else:
        print(f"Migration ({'DRY-RUN' if dry_run else 'APPLY'}):")
        print(f"  Discovered: {out.get('total_discovered', len(out.get('results', [])))}")
        for r in out.get("results", []):
            print(f"  [{r['status']}] {r['role']}/{r['epic_id']}: {len(r['moved'])} files moved")
        if out.get("errors"):
            print("Errors:")
            for err in out["errors"]:
                print(f"  FAILED {err.get('role', '')}/{err.get('epic_id', '')}: {err.get('error')}")

    if not out.get("ok", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
