"""Orchestrate the one-way memory-bank to task-board projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .card_model import parse_metadata
from .client import TaskBoardClient
from .diff import BoardOp, archive_all_task_ids, compute_ops
from .scan_gates import scan_gates
from .scan_mb import scan_steps
from .workspaces import WorkspaceRef


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Counts and diagnostics from one synchronization pass."""

    sync_generation: int
    operations: tuple[BoardOp, ...]
    errors: tuple[str, ...] = ()

    @property
    def created(self) -> int:
        return sum(operation.kind == "create" for operation in self.operations)

    @property
    def updated(self) -> int:
        return sum(operation.kind == "update" for operation in self.operations)

    @property
    def archived(self) -> int:
        return sum(operation.kind == "archive" for operation in self.operations)


def run_sync(
    workspace_refs: list[WorkspaceRef],
    board_client: TaskBoardClient,
    dry_run: bool = False,
    workspace_id_filter: str | None = None,
) -> SyncResult:
    """Scan workspaces, diff the merged desired set, and apply board changes."""
    selected = (
        [ref for ref in workspace_refs if ref.workspace_id == workspace_id_filter]
        if workspace_id_filter is not None
        else workspace_refs
    )
    steps = scan_steps(selected)
    gates = scan_gates(selected, steps)
    existing = board_client.list_tasks()
    previous_generation = _generation(existing)
    if gates.errors:
        # Roadmap configuration errors are fail-closed: do not apply a partial
        # projection that could hide the missing or corrupt queue state.
        return SyncResult(
            sync_generation=previous_generation,
            operations=(),
            errors=(*steps.errors, *gates.errors),
        )
    generation = previous_generation + 1
    operations = compute_ops(
        steps,
        existing,
        gates,
        sync_generation=generation,
    )
    archive_all_ids = archive_all_task_ids(existing, gates)
    if any(gate.archive_all for gate in gates):
        operations = [
            operation
            for operation in operations
            if operation.kind != "archive"
            or operation.task_id in archive_all_ids
        ]
        known_archive_ids = {
            operation.task_id
            for operation in operations
            if operation.kind == "archive"
        }
        operations.extend(
            BoardOp("archive", task_id=task_id)
            for task_id in sorted(archive_all_ids - known_archive_ids)
        )
    if not dry_run:
        for operation in operations:
            if operation.kind in {"create", "update"} and operation.card is not None:
                board_client.upsert(operation.card)
            elif operation.kind == "archive" and operation.task_id is not None:
                board_client.archive(operation.task_id)
    return SyncResult(
        sync_generation=generation,
        operations=tuple(operations),
        errors=(*steps.errors, *gates.errors),
    )


def _generation(tasks: list[Any]) -> int:
    """Read the newest sync generation from machine-readable card metadata."""
    generation = 0
    for task in tasks:
        if not task.id.startswith("mb-"):
            continue
        try:
            card = parse_metadata(task.description)
        except (TypeError, ValueError):
            continue
        generation = max(generation, card.sync_generation)
    return generation
