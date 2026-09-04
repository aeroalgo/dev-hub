"""Epic layout resolver (layout v2) for loop and harness."""

import os
from pathlib import Path
from typing import Optional, Union

from loop.schemas.epic_layout_schema import EpicLayoutKind, EpicLayoutResolveRequest


def get_project_root() -> Path:
    root = os.environ.get("PROJECT_ROOT")
    if root:
        return Path(root)
    return Path.cwd()


def normalize_role_dir(role: str) -> str:
    """Canonical FS role under memory-bank/ (lowercase; integ → integration)."""
    value = str(role or "").strip().lower()
    if not value:
        raise ValueError("role is required")
    if value == "integ":
        return "integration"
    if value not in {"back", "front", "integration"}:
        raise ValueError(
            f"Unknown role dir {role!r}: expected back|front|integ|integration"
        )
    return value


def resolve(
    role: str,
    epic_id: str,
    kind: Union[EpicLayoutKind, str],
    step_id: Optional[str] = None,
    step_slug: Optional[str] = None,
    ext: Optional[str] = None,
    project_root: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve a memory-bank path according to epic-layout v2.

    Layout v2 structure (yaml/md split ONLY under plan/decompose):
      memory-bank/{role}/plan/{epic_id}/md/plan.md
      memory-bank/{role}/plan/{epic_id}/md/decompose-index.md
      memory-bank/{role}/plan/{epic_id}/yaml/decompose-index.yaml
      memory-bank/{role}/plan/{epic_id}/yaml/steps/{step_filename}
      memory-bank/{role}/implement/{epic_id}/{step_filename}
      memory-bank/{role}/qa/{epic_id}/qa.yaml
      memory-bank/{role}/analyze/{epic_id}/analyze.yaml
      memory-bank/{role}/audit/{epic_id}/audit.yaml
    """
    if isinstance(kind, str):
        try:
            kind_enum = EpicLayoutKind(kind)
        except ValueError:
            raise ValueError(f"Unknown EpicLayoutKind: {kind!r}")
    elif isinstance(kind, EpicLayoutKind):
        kind_enum = kind
    else:
        raise ValueError(f"Unknown EpicLayoutKind: {kind!r}")

    def _validate_segment(name: str, val: Optional[str]) -> None:
        if val is None:
            return
        if "/" in val or "\\" in val or ".." in val:
            raise ValueError(f"Invalid characters in {name}: {val!r}")

    role_dir = normalize_role_dir(role)
    _validate_segment("role", role_dir)
    _validate_segment("epic_id", epic_id)
    _validate_segment("step_id", step_id)
    _validate_segment("step_slug", step_slug)
    _validate_segment("ext", ext)

    root = Path(project_root) if project_root is not None else get_project_root()
    base = root / "memory-bank" / role_dir

    def format_step_file(s_id: Optional[str], s_slug: Optional[str], default_ext: str = "yaml") -> str:
        if not s_id:
            raise ValueError("step_id is required for step resolution")
        extension = ext.lstrip(".") if ext else default_ext
        if s_slug:
            return f"{s_id}-{s_slug}.{extension}"
        return f"{s_id}.{extension}"

    if kind_enum == EpicLayoutKind.PLAN_MD:
        return base / "plan" / epic_id / "md" / "plan.md"
    elif kind_enum == EpicLayoutKind.DECOMPOSE_INDEX_MD:
        return base / "plan" / epic_id / "md" / "decompose-index.md"
    elif kind_enum == EpicLayoutKind.DECOMPOSE_INDEX_YAML:
        return base / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    elif kind_enum == EpicLayoutKind.DECOMPOSE_STEP:
        step_filename = format_step_file(step_id, step_slug, default_ext="yaml")
        return base / "plan" / epic_id / "yaml" / "steps" / step_filename
    elif kind_enum == EpicLayoutKind.IMPLEMENT_STEP:
        step_filename = format_step_file(step_id, step_slug, default_ext="yaml")
        return base / "implement" / epic_id / step_filename
    elif kind_enum == EpicLayoutKind.QA_YAML:
        return base / "qa" / epic_id / "qa.yaml"
    elif kind_enum == EpicLayoutKind.ANALYZE_YAML:
        return base / "analyze" / epic_id / "analyze.yaml"
    elif kind_enum == EpicLayoutKind.AUDIT_YAML:
        return base / "audit" / epic_id / "audit.yaml"
    else:
        raise ValueError(f"Unhandled EpicLayoutKind: {kind_enum}")


def resolve_request(req: EpicLayoutResolveRequest, project_root: Optional[Union[str, Path]] = None) -> Path:
    return resolve(
        role=req.role,
        epic_id=req.plan_id,
        kind=req.kind,
        step_id=req.step_id,
        step_slug=req.step_slug,
        ext=req.ext,
        project_root=project_root,
    )


def discover_v2_epics(cwd: Optional[Union[str, Path]] = None) -> list[tuple[str, str]]:
    """Discover epics in v2 layout across memory-bank/{role}/plan/{epic_id}."""
    root = Path(cwd) if cwd is not None else get_project_root()
    mb = root / "memory-bank"
    if not mb.exists() or not mb.is_dir():
        return []

    epics_found: set[tuple[str, str]] = set()
    for role_dir in sorted(mb.iterdir()):
        if not role_dir.is_dir() or role_dir.name.startswith("."):
            continue
        try:
            role = normalize_role_dir(role_dir.name)
        except ValueError:
            continue
        if role_dir.name != role:
            continue
        plan_dir = role_dir / "plan"
        if not plan_dir.exists() or not plan_dir.is_dir():
            continue
        for child in sorted(plan_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            # A v2 epic plan dir must have md/ or yaml/ or decompose index / plan files
            if (child / "yaml").is_dir() or (child / "md").is_dir():
                epics_found.add((role, child.name))
            elif (child / "plan.md").is_file():
                epics_found.add((role, child.name))
            elif (child / "decompose-index.yaml").is_file() or (child / "decompose-index.md").is_file():
                epics_found.add((role, child.name))

    return sorted(list(epics_found))

