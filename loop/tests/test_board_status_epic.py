from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from loop.board_sync.board_status import board_status_for_epic
from loop.board_sync.epic_resolver import EpicNextAction
from loop.board_sync.scan_epics import EpicWorkItem
from loop.board_sync.workspaces import WorkspaceRef


def test_board_status_epic() -> None:
    ref = WorkspaceRef(path=Path("/tmp"), workspace_id="ws")

    unresolved_action = MagicMock(spec=EpicNextAction)
    unresolved_action.phase = "IMPLEMENT"

    resolved_action = MagicMock(spec=EpicNextAction)
    resolved_action.phase = "DONE"

    # rank=0 + unresolved -> running
    item_running = EpicWorkItem(
        role="back",
        epic_id="T-001",
        workspace_ref=ref,
        next_action=unresolved_action,
        roadmap_rank=0,
    )
    assert board_status_for_epic(item_running) == "running"

    # rank=1 + unresolved -> backlog
    item_backlog = EpicWorkItem(
        role="back",
        epic_id="T-002",
        workspace_ref=ref,
        next_action=unresolved_action,
        roadmap_rank=1,
    )
    assert board_status_for_epic(item_backlog) == "backlog"

    # epic_done -> todo
    item_done = EpicWorkItem(
        role="back",
        epic_id="T-003",
        workspace_ref=ref,
        next_action=resolved_action,
        roadmap_rank=0,
    )
    assert board_status_for_epic(item_done) == "todo"
