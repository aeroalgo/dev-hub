"""Compute one-way task-board changes for memory-bank cards."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from .body_loaders import load_gate_body, load_step_body
from .board_status import board_status_for_epic
from .card_model import (
    _FOOTER_DELIMITER,
    CardKind,
    EpicCard,
    GateCard,
    StepCard,
    build_prompt,
    build_title,
    compose_description,
    parse_metadata,
    serialize_metadata,
    stable_id,
)
from .scan_epics import EpicWorkItem
from .scan_gates import GateWorkItem
from .scan_mb import WorkItem
from pathlib import Path


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


_PRE_IMPL_PHASES = frozenset({"PLAN", "DECOMPOSE", "CLARIFY", "ANALYZE"})


def status_for_work_item(item: WorkItem) -> str:
    """Return task-board status for a WorkItem step."""
    if item.status in {"in_progress", "active", "blocked"}:
        return "running"
    return "todo"


def status_for_gate(item: GateWorkItem) -> str:
    """Return task-board status for a GateWorkItem."""
    phase_upper = item.gate_phase.upper()
    if phase_upper == "ROADMAP" or phase_upper in _PRE_IMPL_PHASES:
        return "backlog"
    return "todo"


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
    body: str | None = None
    if item.shard_rel:
        shard_path = item.workspace_ref.path / item.shard_rel
        body, _diag = load_step_body(shard_path)

    return BoardTask(
        id=stable_id(
            kind=card.card_kind,
            ws_id=card.workspace_id,
            role=card.role,
            epic_id=card.epic_id,
            step_id=card.step_id,
        ),
        title=build_title(card, item.title),
        description=compose_description(body, card),
        prompt=build_prompt(card),
        workspace_id=card.workspace_id,
        status=status_for_work_item(item),
    )


def epic_work_item_card(item: EpicWorkItem, sync_generation: int) -> BoardTask:
    """Build a task-board card for an active or completed epic."""
    action = item.next_action
    card = EpicCard(
        project_root=str(item.workspace_ref.path),
        workspace_id=item.workspace_ref.workspace_id,
        role=item.role,
        epic_id=item.epic_id,
        next_command=action.next_command,
        next_step_id=action.next_step_id or "",
        progress_summary=f"phase={action.phase}",
        roadmap_rank=item.roadmap_rank if item.roadmap_rank is not None else -1,
        sync_generation=sync_generation,
    )
    return BoardTask(
        id=stable_id(
            kind=card.card_kind,
            ws_id=card.workspace_id,
            role=card.role,
            epic_id=card.epic_id,
        ),
        title=f"[{card.role}] {card.epic_id}",
        description=compose_description(None, card),
        prompt=build_prompt(card),
        workspace_id=card.workspace_id,
        status=board_status_for_epic(item),
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
    body: str | None = None
    if item.gate_phase.upper() not in {"AUDIT", "QA", "BUGFIX"}:
        plan_path = item.workspace_ref.path / item.plan_rel if item.plan_rel else None
        body = load_gate_body(plan_path, item.reason_code)

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
        description=compose_description(body, card),
        prompt=build_prompt(card),
        workspace_id=card.workspace_id,
        status=status_for_gate(item),
    )


def desired_cards(
    workitems: Iterable[WorkItem | EpicWorkItem],
    gates: Iterable[GateWorkItem],
    sync_generation: int = 1,
) -> list[BoardTask]:
    """Return the merged desired set of epic and gate cards."""
    epic_cards: list[BoardTask] = []
    step_cards: list[BoardTask] = []
    for item in workitems:
        if isinstance(item, EpicWorkItem):
            epic_cards.append(epic_work_item_card(item, sync_generation))
        elif isinstance(item, WorkItem):
            step_cards.append(work_item_card(item, sync_generation))

    return [
        *epic_cards,
        *step_cards,
        *[gate_card(item, sync_generation) for item in gates if not item.archive_all],
    ]


def archive_all_task_ids(
    existing: Iterable[BoardTask],
    gates: Iterable[GateWorkItem] = (),
    step_era_archive: bool = False,
) -> set[str]:
    """Select existing cards covered by terminal DONE signal or step era migration."""
    scopes = {
        (gate.workspace_ref.workspace_id, gate.role, gate.epic_id)
        for gate in gates
        if gate.archive_all and gate.epic_id is not None
    }

    result: set[str] = set()
    for task in existing:
        if not task.id.startswith("mb-"):
            continue
        try:
            card = parse_metadata(task.description)
        except (TypeError, ValueError):
            continue

        if step_era_archive and card.card_kind == CardKind.STEP:
            result.add(task.id)
            continue

        if scopes and (card.workspace_id, card.role, getattr(card, "epic_id", None)) in scopes:
            result.add(task.id)
    return result


def compute_ops(
    workitems: Iterable[WorkItem | EpicWorkItem] | Iterable[BoardTask],
    existing: Iterable[BoardTask],
    gates: Iterable[GateWorkItem] = (),
    *,
    sync_generation: int = 1,
) -> list[BoardOp]:
    """Compute create/update/archive operations, ignoring non-``mb-`` tasks."""
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
    if _FOOTER_DELIMITER in description:
        body, _ = description.rsplit(_FOOTER_DELIMITER, 1)
    elif _FOOTER_DELIMITER.lstrip("\n") in description:
        body, _ = description.rsplit(_FOOTER_DELIMITER.lstrip("\n"), 1)
    else:
        body = None
    return compose_description(body, replace(metadata, sync_generation=0))
