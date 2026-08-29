from __future__ import annotations

from pathlib import Path

from loop.board_sync.card_model import StepCard, serialize_metadata, stable_id
from loop.board_sync.diff import BoardTask, compute_ops
from loop.board_sync.scan_mb import WorkItem
from loop.board_sync.workspaces import WorkspaceRef

PROJECT = Path("/workspaces/demo")
WORKSPACE = WorkspaceRef(PROJECT, "demo")


def _item(title: str = "First pending") -> WorkItem:
    return WorkItem(
        role="back",
        epic_id="T-DEMO",
        step_id="s01",
        status="pending",
        decompose_rel="memory-bank/back/plan/decompose-T-DEMO/index.yaml",
        title=title,
        workspace_ref=WORKSPACE,
    )


def _task(item: WorkItem, *, title: str | None = None) -> BoardTask:
    card = StepCard(
        project_root=str(item.workspace_ref.path),
        workspace_id=item.workspace_ref.workspace_id,
        role=item.role,
        epic_id=item.epic_id,
        step_id=item.step_id,
        decompose_rel=item.decompose_rel,
        phase="IMPLEMENT",
        sync_generation=1,
    )
    return BoardTask(
        id=stable_id(
            kind="step",
            ws_id=item.workspace_ref.workspace_id,
            role=item.role,
            epic_id=item.epic_id,
            step_id=item.step_id,
        ),
        title=title or f"[BACK] T-DEMO s01 — {item.title}",
        description=serialize_metadata(card),
        prompt="BACK IMPLEMENT",
        workspace_id=item.workspace_ref.workspace_id,
        status="todo",
    )


def test_diff_upsert_new() -> None:
    ops = compute_ops([_item()], [])

    assert [(op.kind, op.card.id) for op in ops] == [
        ("create", "mb-demo-back-t-demo-s01")
    ]


def test_diff_update_changed() -> None:
    ops = compute_ops([_item("Renamed")], [_task(_item())])

    assert len(ops) == 1
    assert ops[0].kind == "update"
    assert ops[0].card.title.endswith("Renamed")


def test_diff_archive_vanished() -> None:
    task = _task(_item())
    ops = compute_ops([], [task])

    assert [(op.kind, op.task_id) for op in ops] == [("archive", task.id)]


def test_diff_idempotent_skip() -> None:
    item = _item()
    task = _task(item)
    ops = compute_ops([item], [task])

    assert ops == []


def test_diff_non_mb_ignored() -> None:
    manual = BoardTask(
        id="manual-1",
        title="Keep me",
        description="manual",
        prompt="",
        workspace_id="demo",
    )

    assert compute_ops([], [manual]) == []
