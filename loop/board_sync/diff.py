"""Compute one-way task-board changes for memory-bank cards."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .card_model import (
    GateCard,
    StepCard,
    build_prompt,
    build_title,
    parse_metadata,
    serialize_metadata,
    stable_id,
)
from .scan_gates import GateWorkItem
from .scan_mb import WorkItem


@dataclass(frozen=True, slots=True)
class BoardTask:
    """Small task-board representation used by clients and the diff."""

    id: str
    title: str
    description: str
    prompt: str
    workspace_id: str = ""
    status: str = "todo"


@dataclass(frozen=True, slots=True)
class BoardOp:
    """A create/update or archive operation for one board task."""

    kind: str
    card: BoardTask | None = None
    task_id: str | None = None


def work_item_card(item: WorkItem, sync_generation: int) -> BoardTask:
    """Build a task-board card for an active decomposition step."""
    card = StepCard(
        project_root=str(item.workspace_ref.path),
        workspace_id=item.workspace_ref.workspace_id,
        role=item.role,
        epic_id=item.epic_id,
        step_id=item.step_id,
        decompose_rel=item.decompose_rel,
        phase="IMPLEMENT",
        sync_generation=sync_generation,
    )
    return BoardTask(
        id=stable_id(
            kind=card.card_kind,
            ws_id=card.workspace_id,
            role=card.role,
            epic_id=card.epic_id,
            step_id=card.step_id,
        ),
        title=build_title(card, item.title),
        description=serialize_metadata(card),
        prompt=build_prompt(card),
        workspace_id=card.workspace_id,
        status="running" if item.status == "in_progress" else "todo",
    )


def gate_card(item: GateWorkItem, sync_generation: int) -> BoardTask:
    """Build a task-board card for a workflow gate."""
    card = GateCard(
        project_root=str(item.workspace_ref.path),
        workspace_id=item.workspace_ref.workspace_id,
        role=item.role,
        epic_id=item.epic_id,
        gate_phase=item.gate_phase,
        decompose_rel=item.decompose_rel,
        phase=item.gate_phase,
        sync_generation=sync_generation,
        reason_code=item.reason_code,
    )
    return BoardTask(
        id=stable_id(
            kind=card.card_kind,
            ws_id=card.workspace_id,
            role=card.role,
            epic_id=card.epic_id,
            gate_phase=card.gate_phase,
        ),
        title=build_title(
            card,
            project_label=item.workspace_ref.workspace_id,
            next_epic_id=item.reason_code if card.gate_phase.upper() == "ROADMAP" else None,
        ),
        description=serialize_metadata(card),
        prompt=build_prompt(card),
        workspace_id=card.workspace_id,
        status="todo",
    )


def desired_cards(
    workitems: Iterable[WorkItem],
    gates: Iterable[GateWorkItem],
    sync_generation: int = 1,
) -> list[BoardTask]:
    """Return the merged desired set of step and gate cards."""
    return [
        *[work_item_card(item, sync_generation) for item in workitems],
        *[gate_card(item, sync_generation) for item in gates if not item.archive_all],
    ]


def archive_all_task_ids(
    existing: Iterable[BoardTask],
    gates: Iterable[GateWorkItem],
) -> set[str]:
    """Select existing cards covered by an epic's terminal DONE signal."""
    scopes = {
        (gate.workspace_ref.workspace_id, gate.role, gate.epic_id)
        for gate in gates
        if gate.archive_all and gate.epic_id is not None
    }
    if not scopes:
        return set()

    result: set[str] = set()
    for task in existing:
        if not task.id.startswith("mb-"):
            continue
        try:
            card = parse_metadata(task.description)
        except (TypeError, ValueError):
            continue
        if (card.workspace_id, card.role, getattr(card, "epic_id", None)) in scopes:
            result.add(task.id)
    return result


def compute_ops(
    workitems: Iterable[WorkItem] | Iterable[BoardTask],
    existing: Iterable[BoardTask],
    gates: Iterable[GateWorkItem] = (),
    *,
    sync_generation: int = 1,
) -> list[BoardOp]:
    """Compute create/update/archive operations, ignoring non-``mb-`` tasks.

    The two-argument form accepts desired ``BoardTask`` objects for callers that
    already materialized cards; the orchestrator passes WorkItems and gates.
    """
    desired = list(workitems)
    if desired and isinstance(desired[0], BoardTask):
        cards = desired  # type: ignore[assignment]
    else:
        cards = desired_cards(desired, gates, sync_generation)  # type: ignore[arg-type]

    current = {task.id: task for task in existing if task.id.startswith("mb-")}
    operations: list[BoardOp] = []
    for card in cards:
        old = current.pop(card.id, None)
        if old is None:
            operations.append(BoardOp("create", card=card))
        elif not _same_content(old, card):
            operations.append(BoardOp("update", card=card))
    operations.extend(BoardOp("archive", task_id=task_id) for task_id in current)
    return operations


def _same_content(left: BoardTask, right: BoardTask) -> bool:
    """Compare semantic card fields without sync-generation metadata."""
    return replace(left, description=_without_generation(left.description)) == replace(
        right, description=_without_generation(right.description)
    )


def _without_generation(description: str) -> str:
    """Normalize card metadata so generation-only changes are ignored."""
    try:
        metadata = parse_metadata(description)
    except (TypeError, ValueError):
        return description
    return serialize_metadata(replace(metadata, sync_generation=0))
