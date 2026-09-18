"""Scan memory-bank epics for task-board projection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from loop.paths.epic_layout import discover_v2_epics
from loop.roadmap_queue import parse_roadmap_queue
from loop.board_sync.card_model import CardKind
from loop.board_sync.epic_resolver import EpicNextAction, resolve_epic_next_action
from loop.board_sync.scan_mb import _ROLES
from loop.board_sync.workspaces import WorkspaceRef


@dataclass(frozen=True, slots=True)
class EpicWorkItem:
    """An active or completed epic projected onto the task board."""

    role: str
    epic_id: str
    workspace_ref: WorkspaceRef
    next_action: EpicNextAction
    roadmap_rank: int | None = None

    @property
    def card_kind(self) -> CardKind:
        return CardKind.EPIC


@dataclass
class ScanEpicsResult(Sequence[EpicWorkItem]):
    """Collection of scanned epic items with diagnostics."""

    items: list[EpicWorkItem]
    errors: list[str]

    def __init__(
        self,
        items: list[EpicWorkItem] | None = None,
        *,
        errors: list[str] | None = None,
    ) -> None:
        self.items = items or []
        self.errors = errors or []

    def __getitem__(self, index: int | slice) -> EpicWorkItem | list[EpicWorkItem]:  # type: ignore[override]
        return self.items[index]

    def __len__(self) -> int:
        return len(self.items)


def scan_epics(workspace_refs: list[WorkspaceRef]) -> ScanEpicsResult:
    """Scan all epics across roles and workspaces for board projection."""
    result = ScanEpicsResult()

    for ws_ref in workspace_refs:
        mb_dir = ws_ref.path / "memory-bank"
        if not mb_dir.is_dir():
            continue

        for role in _ROLES:
            queue_file = mb_dir / role / "roadmap" / "queue.yaml"
            queue_data: list[dict] = []
            if queue_file.is_file():
                parsed = parse_roadmap_queue(ws_ref.path, queue_rel=str(queue_file.relative_to(ws_ref.path)))
                if parsed.get("ok"):
                    queue_data = parsed.get("queue", [])
                else:
                    err = parsed.get("error") or parsed.get("reason") or "queue parse error"
                    result.errors.append(f"{ws_ref.path}: {err}")

            epic_ranks: dict[str, int] = {}
            for idx, item in enumerate(queue_data):
                if isinstance(item, dict) and "id" in item:
                    epic_ranks[item["id"]] = idx

            role_dir = mb_dir / role
            if not role_dir.is_dir():
                continue

            epic_ids: set[str] = set()

            # The layout resolver owns v2 plan/index discovery. Flat plan names
            # Non-canonical plan directories are not live sources.
            epic_ids.update(
                discovered_id
                for discovered_role, discovered_id in discover_v2_epics(ws_ref.path)
                if discovered_role == role
            )

            # Find epics in implement/
            impl_dir = role_dir / "implement"
            if impl_dir.is_dir():
                for p in impl_dir.iterdir():
                    if p.is_dir():
                        epic_id = p.name
                        if epic_id:
                            epic_ids.add(epic_id)

            sorted_epic_ids = sorted(epic_ids)
            for epic_id in sorted_epic_ids:
                next_action = resolve_epic_next_action(
                    project=ws_ref.path,
                    role=role,
                    epic_id=epic_id,
                )

                rank: int | None = epic_ranks.get(epic_id)

                result.items.append(
                    EpicWorkItem(
                        role=role,
                        epic_id=epic_id,
                        workspace_ref=ws_ref,
                        next_action=next_action,
                        roadmap_rank=rank,
                    )
                )

    return result
