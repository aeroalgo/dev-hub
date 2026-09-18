"""Scan active memory-bank decomposition steps for board projection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.hooks.epic_index import load_index_yaml, steps_from_doc
import yaml

from .workspaces import WorkspaceRef

_ACTIVE_STATUSES = frozenset({"pending", "in_progress", "active", "blocked"})
_ROLES = ("back", "front", "integration")


@dataclass(frozen=True, slots=True)
class WorkItem:
    """An active decomposition step belonging to one registered workspace."""

    role: str
    epic_id: str
    step_id: str
    status: str
    decompose_rel: str
    title: str
    workspace_ref: WorkspaceRef
    shard_rel: str | None = None


class ScanResult(list[WorkItem]):
    """List-compatible scan result carrying non-fatal project diagnostics."""

    def __init__(self, items: list[WorkItem] | None = None, *, errors: list[str] | None = None) -> None:
        super().__init__(items or [])
        self.errors = errors or []

    @property
    def items(self) -> list[WorkItem]:
        """Return the collected items as a regular list."""

        return list(self)


def scan_steps(workspace_refs: list[WorkspaceRef]) -> ScanResult:
    """Return active step rows from every eligible workspace.

    A malformed index invalidates its whole workspace, records one diagnostic,
    and does not prevent the remaining workspaces from being scanned. A
    workspace without ``memory-bank/`` is ignored because eligibility may have
    changed since discovery.
    """

    result = ScanResult()
    for workspace_ref in workspace_refs:
        project_root = workspace_ref.path
        memory_bank = project_root / "memory-bank"
        if not memory_bank.is_dir():
            continue

        indexes = _index_paths(memory_bank)
        project_items: list[WorkItem] = []
        project_error: str | None = None
        for index_path in indexes:
            try:
                project_items.extend(_parse_index(index_path, workspace_ref))
            except (OSError, TypeError, UnicodeError, ValueError, yaml.YAMLError) as exc:
                project_error = f"{index_path}: {exc}"
                break
        if project_error is not None:
            result.errors.append(project_error)
            continue
        result.extend(project_items)
    return result


def _index_paths(memory_bank: Path) -> list[Path]:
    """Return role-scoped decomposition indexes in stable order (layout v2)."""

    paths = []
    for role in _ROLES:
        plan_dir = memory_bank / role / "plan"
        if not plan_dir.is_dir():
            continue
        # v2 layout: plan/<epic_id>/yaml/decompose-index.yaml
        v2_paths = sorted(plan_dir.glob("*/yaml/decompose-index.yaml"))
        paths.extend(v2_paths)
    return paths


def _parse_index(path: Path, workspace_ref: WorkspaceRef) -> list[WorkItem]:
    """Load one validated decomposition index and return its active rows."""

    payload = load_index_yaml(path)
    if payload is None:
        raise ValueError("decompose index is missing")
    epic_id = str(payload["plan_id"])
    steps = steps_from_doc(payload)

    role = _role_for_index(path)
    decompose_rel = path.relative_to(workspace_ref.path).as_posix()
    result: list[WorkItem] = []
    for step in steps:
        step_id = step.get("id")
        status = step.get("status")
        if status not in _ACTIVE_STATUSES:
            continue
        title = step.get("title", "")
        file_name = step["file"]
        shard_dir = path.parent / "steps"
        shard_rel = f"{shard_dir.relative_to(workspace_ref.path)}/{file_name}"
        result.append(
            WorkItem(
                role=role,
                epic_id=epic_id,
                step_id=step_id,
                status=status,
                decompose_rel=decompose_rel,
                title=title,
                workspace_ref=workspace_ref,
                shard_rel=shard_rel,
            )
        )
    return result


def _role_for_index(path: Path) -> str:
    """Extract the supported memory-bank role from an index path."""

    for role in _ROLES:
        if role in path.parts:
            return role
    raise ValueError(f"unsupported memory-bank role for index: {path}")
