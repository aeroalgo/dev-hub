"""Board status assignment logic for epics based on roadmap rank and next action."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .scan_epics import EpicWorkItem

BoardStatus = Literal["running", "backlog", "todo", "done"]


def board_status_for_epic(epic_item: EpicWorkItem) -> BoardStatus:
    """Determine board column status for an epic item.

    Rules:
    - rank == 0 and not resolved (phase is not DONE / NEXT_EPIC) -> running
    - rank > 0 -> backlog
    - phase is DONE / NEXT_EPIC -> todo
    - rank is None (or fallback unranked unresolved) -> backlog
    """
    phase_upper = epic_item.next_action.phase.upper()
    if phase_upper in {"DONE", "NEXT_EPIC"}:
        return "todo"
    if epic_item.roadmap_rank == 0:
        return "running"
    return "backlog"
