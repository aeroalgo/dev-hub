"""Unified epic path resolver with workflow pack parameter support."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional, Union

from loop.paths.pack_layout import resolve_mb_root
from loop.workflow.schemas import WorkflowPack


class EpicPathKind(str, Enum):
    """Supported artifact kinds for epic path resolution."""
    PLAN = "plan"
    DECOMPOSE = "decompose"
    IMPLEMENT = "implement"
    QA = "qa"
    ANALYZE = "analyze"
    AUDIT = "audit"


def _normalize_role_dir(role: str) -> str:
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


def _validate_segment(name: str, val: Optional[str]) -> None:
    if val is None:
        return
    if "/" in val or "\\" in val or ".." in val:
        raise ValueError(f"Invalid characters in {name}: {val!r}")


def resolve_epic_path(
    kind: Union[EpicPathKind, str],
    epic_id: str,
    pack: Optional[WorkflowPack] = None,
    role: str = "back",
    step_id: Optional[str] = None,
    step_slug: Optional[str] = None,
    ext: Optional[str] = None,
    cwd: Optional[Union[Path, str]] = None,
    hub_root: Optional[Union[Path, str]] = None,
) -> Path:
    """Resolve pack-relative epic artifact path.

    Resolves paths relative to `resolve_mb_root(cwd, pack)` / `{role}`:
    - plan: mb_root / role / 'plan' / epic_id / 'md' (or file if step_id provided)
    - decompose: mb_root / role / 'plan' / epic_id / 'yaml' / 'steps' (or step file if step_id provided)
    - implement: mb_root / role / 'implement' / epic_id (or step file if step_id provided)
    - qa: mb_root / role / 'qa' / epic_id / 'qa.yaml' (or qa dir)
    - analyze: mb_root / role / 'analyze' / epic_id / 'analyze.yaml' (or analyze dir)
    - audit: mb_root / role / 'audit' / epic_id / 'audit.yaml' (or audit dir)
    """
    if isinstance(kind, str):
        try:
            kind_enum = EpicPathKind(kind)
        except ValueError:
            raise ValueError(f"Unknown EpicPathKind: {kind!r}")
    elif isinstance(kind, EpicPathKind):
        kind_enum = kind
    else:
        raise ValueError(f"Unknown EpicPathKind: {kind!r}")

    if not epic_id or not str(epic_id).strip():
        raise ValueError("epic_id is required")

    role_dir = _normalize_role_dir(role)
    _validate_segment("role", role_dir)
    _validate_segment("epic_id", epic_id)
    _validate_segment("step_id", step_id)
    _validate_segment("step_slug", step_slug)
    _validate_segment("ext", ext)

    mb_root = resolve_mb_root(cwd=cwd, pack=pack, hub_root=hub_root)
    base = mb_root / role_dir

    def format_step_file(s_id: Optional[str], s_slug: Optional[str], default_ext: str = "yaml") -> str:
        if not s_id:
            raise ValueError("step_id is required for step file resolution")
        extension = ext.lstrip(".") if ext else default_ext
        if s_slug:
            return f"{s_id}-{s_slug}.{extension}"
        return f"{s_id}.{extension}"

    if kind_enum == EpicPathKind.PLAN:
        plan_md_dir = base / "plan" / epic_id / "md"
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="md")
            return plan_md_dir / filename
        return plan_md_dir

    elif kind_enum == EpicPathKind.DECOMPOSE:
        steps_dir = base / "plan" / epic_id / "yaml" / "steps"
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="yaml")
            return steps_dir / filename
        return steps_dir

    elif kind_enum == EpicPathKind.IMPLEMENT:
        impl_dir = base / "implement" / epic_id
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="yaml")
            return impl_dir / filename
        return impl_dir

    elif kind_enum == EpicPathKind.QA:
        qa_dir = base / "qa" / epic_id
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="yaml")
            return qa_dir / filename
        return qa_dir / "qa.yaml"

    elif kind_enum == EpicPathKind.ANALYZE:
        analyze_dir = base / "analyze" / epic_id
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="yaml")
            return analyze_dir / filename
        return analyze_dir / "analyze.yaml"

    elif kind_enum == EpicPathKind.AUDIT:
        audit_dir = base / "audit" / epic_id
        if step_id:
            filename = format_step_file(step_id, step_slug, default_ext="yaml")
            return audit_dir / filename
        return audit_dir / "audit.yaml"

    raise ValueError(f"Unhandled EpicPathKind: {kind_enum}")
