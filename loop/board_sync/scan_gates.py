"""Emit pre- and post-implementation memory-bank board gates."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .card_model import CardKind
from .scan_mb import WorkItem
from .workspaces import WorkspaceRef

_LOOP = Path(__file__).resolve().parents[1]
if str(_LOOP) not in sys.path:
    sys.path.insert(0, str(_LOOP))

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic import reduce_epic_lifecycle

_ACTIVE_STATUSES = frozenset({"pending", "in_progress", "active", "blocked"})
_COMPLETED_STATUSES = frozenset({"completed", "done"})
_POST_PHASES = frozenset({"AUDIT", "QA", "BUGFIX", "REFLECT"})
_ROLES = ("back", "front", "integration")


@dataclass(frozen=True, slots=True)
class GateWorkItem:
    """A workflow gate projected as a board item."""

    role: str
    epic_id: str | None
    gate_phase: str
    workspace_ref: WorkspaceRef
    decompose_rel: str | None = None
    reason_code: str | None = None
    archive_all: bool = False

    @property
    def card_kind(self) -> CardKind:
        return CardKind.GATE

    @property
    def phase(self) -> str:
        return self.gate_phase


class GateScanResult(list[GateWorkItem]):
    """List-compatible gate scan carrying configuration diagnostics."""

    def __init__(
        self,
        items: list[GateWorkItem] | None = None,
        *,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(items or [])
        self.errors = errors or []


def scan_gates(
    workspace_refs: list[WorkspaceRef],
    step_workitems: Iterable[WorkItem],
) -> GateScanResult:
    """Return at most one applicable gate for each workspace/epic.

    Active step rows suppress post-implement gates for the same epic. Pre-gates
    are derived from the plan/decompose files, while lifecycle decisions are
    delegated to the loop reducer rather than reimplemented here.
    """

    steps = list(step_workitems)
    by_workspace_epic: dict[tuple[Path, str, str], list[WorkItem]] = {}
    for item in steps:
        key = (item.workspace_ref.path, item.role, item.epic_id)
        by_workspace_epic.setdefault(key, []).append(item)

    result: list[GateWorkItem] = []
    errors: list[str] = []
    for workspace_ref in workspace_refs:
        for role in _ROLES:
            project = workspace_ref.path
            queued_epics = _queued_epics(project, role)
            for epic_id in _known_epics(project, role, steps):
                key = (project, role, epic_id)
                epic_steps = by_workspace_epic.get(key, [])
                decompose = _find_decompose(project, role, epic_id)
                plan = _plan_path(project, role, epic_id)

                # Queue entries are the only source for a PLAN gate. A
                # decompose index can still be scanned in an unqueued fixture
                # (and is useful for lifecycle projection) without inventing a
                # PLAN gate for it.
                if decompose is None or (epic_id in queued_epics and plan is None):
                    result.extend(
                        _pre_gates(
                            workspace_ref,
                            role,
                            epic_id,
                            decompose,
                            require_plan=epic_id in queued_epics,
                        )
                    )
                    continue

                payload = _load_decompose(decompose)
                statuses = [
                    step.get("status")
                    for step in payload.get("steps", [])
                    if isinstance(step, dict)
                ]
                has_active = _has_active_steps(epic_steps)
                has_completed = any(
                    status in _COMPLETED_STATUSES for status in statuses
                )
                if has_active:
                    # Active implementation steps are the board projection for
                    # this epic; do not duplicate them with a pre-implement gate.
                    continue
                if not has_completed:
                    result.extend(
                        _pre_gates(
                            workspace_ref,
                            role,
                            epic_id,
                            decompose,
                            require_plan=epic_id in queued_epics,
                        )
                    )
                    continue

                lifecycle = reduce_epic_lifecycle(project, role, epic_id)
                phase = str(lifecycle.get("phase", "")).upper()
                if phase in _POST_PHASES or phase == "DONE":
                    gate_phase = (
                        "BUGFIX"
                        if lifecycle.get("reason_code") == "qa_failed"
                        else phase
                    )
                    result.append(
                        GateWorkItem(
                            role=role,
                            epic_id=epic_id,
                            gate_phase=gate_phase,
                            workspace_ref=workspace_ref,
                            decompose_rel=_relative(decompose, project),
                            reason_code=lifecycle.get("reason_code"),
                            archive_all=phase == "DONE",
                        )
                    )
        roadmap_gates, roadmap_errors = _roadmap_gate(workspace_ref, steps)
        result.extend(roadmap_gates)
        errors.extend(roadmap_errors)
    return GateScanResult(_dedupe(result), errors=errors)


def _queued_epics(project: Path, role: str) -> set[str]:
    """Return epic ids declared by the role's roadmap queue."""
    plan_dir = project / "memory-bank" / role / "plan"
    result: set[str] = set()
    for queue in plan_dir.glob("roadmap-*.queue.yaml") if plan_dir.is_dir() else []:
        try:
            payload = yaml.safe_load(queue.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            continue
        entries = payload.get("queue") if isinstance(payload, dict) else None
        if isinstance(entries, list):
            result.update(
                entry["id"]
                for entry in entries
                if isinstance(entry, dict) and isinstance(entry.get("id"), str)
            )
    return result


def _known_epics(project: Path, role: str, steps: list[WorkItem]) -> set[str]:
    result = {
        item.epic_id
        for item in steps
        if item.workspace_ref.path == project and item.role == role
    }
    plan_dir = project / "memory-bank" / role / "plan"
    if plan_dir.is_dir():
        result.update(
            path.name.removeprefix("decompose-")
            for path in plan_dir.glob("decompose-*")
            if path.is_dir()
        )
        for queue in plan_dir.glob("roadmap-*.queue.yaml"):
            try:
                payload = yaml.safe_load(queue.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, yaml.YAMLError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("queue"), list):
                result.update(
                    entry["id"]
                    for entry in payload["queue"]
                    if isinstance(entry, dict) and isinstance(entry.get("id"), str)
                )
    return result


def _find_decompose(project: Path, role: str, epic_id: str) -> Path | None:
    directory = project / "memory-bank" / role / "plan"
    for path in (
        directory / f"decompose-{epic_id}" / "index.yaml",
        directory / f"decompose-{epic_id}" / "index.md",
    ):
        if path.is_file():
            return path
    matches = sorted(directory.glob(f"decompose-{epic_id}-*/index.yaml"))
    return matches[0] if matches else None


def _plan_path(project: Path, role: str, epic_id: str) -> Path | None:
    plan_dir = project / "memory-bank" / role / "plan"
    candidates = [plan_dir / f"plan-{epic_id}.md"]
    candidates.extend(sorted(plan_dir.glob(f"plan-{epic_id}-*.md")))
    return next((path for path in candidates if path.is_file()), None)


def _pre_gates(
    workspace_ref: WorkspaceRef,
    role: str,
    epic_id: str,
    decompose: Path | None,
    *,
    require_plan: bool = False,
) -> list[GateWorkItem]:
    project = workspace_ref.path
    plan = _plan_path(project, role, epic_id)
    if plan is None and require_plan:
        return [
            GateWorkItem(role, epic_id, "PLAN", workspace_ref, reason_code="plan_missing")
        ]
    if decompose is None:
        return [
            GateWorkItem(
                role, epic_id, "DECOMPOSE", workspace_ref, reason_code="decompose_missing"
            )
        ]
    if decompose is None:
        return [
            GateWorkItem(
                role, epic_id, "DECOMPOSE", workspace_ref, reason_code="decompose_missing"
            )
        ]
    payload = _load_decompose(decompose)
    statuses = [step.get("status") for step in payload.get("steps", [])]
    if not any(status in _COMPLETED_STATUSES for status in statuses):
        analyze = _latest_analyze(project, role, epic_id)
        if analyze is None or _critical_count(analyze) > 0:
            return [
                GateWorkItem(
                    role,
                    epic_id,
                    "ANALYZE",
                    workspace_ref,
                    _relative(decompose, project),
                    "analyze_required",
                )
            ]
    if _has_unresolved_critical(plan, project, role, epic_id):
        return [
            GateWorkItem(
                role,
                epic_id,
                "CLARIFY",
                workspace_ref,
                _relative(decompose, project),
                "clarify_required",
            )
        ]
    return []


def _roadmap_gate(
    workspace_ref: WorkspaceRef,
    steps: list[WorkItem],
) -> tuple[list[GateWorkItem], list[str]]:
    if any(item.workspace_ref.path == workspace_ref.path for item in steps):
        return [], []
    try:
        import roadmap_queue

        selection = roadmap_queue.select_next_epic(workspace_ref.path)
    except (ImportError, OSError, ValueError, KeyError) as exc:
        return [], [f"{workspace_ref.path}: roadmap selection failed: {exc}"]
    if not selection.get("ok"):
        error = selection.get("error") or selection.get("reason") or "unknown error"
        return [], [f"{workspace_ref.path}: roadmap selection failed: {error}"]
    if selection.get("complete"):
        return [], []
    entry = selection.get("entry") or {}
    epic_id = entry.get("epic") or entry.get("queue_id")
    if not isinstance(epic_id, str):
        return [], [f"{workspace_ref.path}: roadmap selection returned no epic"]
    return [GateWorkItem("back", None, "ROADMAP", workspace_ref, reason_code=epic_id)], []




def _has_active_steps(items: list[WorkItem]) -> bool:
    return any(item.status in _ACTIVE_STATUSES for item in items)


def _load_decompose(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_analyze(project: Path, role: str, epic_id: str) -> dict[str, Any] | None:
    directories = [
        project / "memory-bank" / role / "analyze" / epic_id,
        project / "memory-bank" / role / "analyze",
    ]
    paths = [path for directory in directories if directory.is_dir() for path in directory.glob("analyze-*.yaml")]
    for path in sorted(paths, reverse=True):
        payload = _load_decompose(path)
        if payload:
            return payload
    return None


def _critical_count(payload: dict[str, Any]) -> int:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    try:
        return int(metrics.get("critical_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _has_unresolved_critical(plan: Path, project: Path, role: str, epic_id: str) -> bool:
    try:
        text = plan.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if "[НУЖНО УТОЧНИТЬ: CRITICAL" not in text:
        return False
    clarify_dir = project / "memory-bank" / role / "clarify"
    for path in sorted(clarify_dir.glob("*.md")) if clarify_dir.is_dir() else []:
        try:
            artifact = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if epic_id in artifact and "Completion Report" in artifact and "defer" not in artifact.lower():
            return False
    return True


def _relative(path: Path | None, root: Path) -> str | None:
    return path.relative_to(root).as_posix() if path is not None else None


def _dedupe(items: list[GateWorkItem]) -> list[GateWorkItem]:
    seen: set[tuple[Path, str, str | None, str]] = set()
    result: list[GateWorkItem] = []
    for item in items:
        key = (item.workspace_ref.path, item.role, item.epic_id, item.gate_phase)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
