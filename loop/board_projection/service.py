from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop.board_projection.card_copy import resolve_card_fields
from loop.board_projection.config import BoardProjectionConfig, load_projection_config
from loop.board_projection.errors import (
    AdapterExecutionError,
    ProjectionConfigError,
    ProjectionError,
    ProviderMismatchError,
)
from loop.board_projection.mapping import (
    BoardEpicMap,
    EpicMapEntry,
    load_board_epic_map,
    resolve_map_path,
    save_board_epic_map,
)
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef, ProjectionResult
from loop.board_projection.registry import get_adapter


def project_epic_phase(
    project_root: Path | str,
    epic_id: str,
    phase: str,
    role: str = "back",
    title: str = "",
    description: str = "",
    kind: str | None = None,
    config_path: Path | str | None = None,
    map_path: Path | str | None = None,
    adapter: BoardProjectionAdapter | None = None,
) -> ProjectionResult:
    """
    Project epic phase to an external board (Bitrix24, Plane).
    Implements:
    - Lazy card creation on first encounter (FR-005)
    - Phase/state transition when card exists (FR-006)
    - Provider mismatch protection fail-closed before any HTTP (BN-004, TM-004, SC-003)
    - Soft-fail on transient or network errors without breaking caller loop (FR-009, BN-006, BN-007, TM-006, SC-004)
    """
    root_path = Path(project_root)
    resolved_config_path = (
        Path(config_path) if config_path is not None else root_path / ".loop" / "board-projection.yaml"
    )
    resolved_map_path = resolve_map_path(project_root=root_path, explicit_path=map_path)

    # 1. Load config
    config, disabled_reason = load_projection_config(resolved_config_path)

    if disabled_reason == "missing_config":
        return ProjectionResult(status="disabled", disabled_reason="missing_config")

    if config is None or config.provider == "none" or disabled_reason == "provider_none":
        return ProjectionResult(status="disabled", disabled_reason="provider_none")

    if disabled_reason:
        raise ProjectionConfigError(
            f"Active board projection provider '{config.provider}' is misconfigured: {disabled_reason}"
        )

    # 2. Check role allowlist
    if not config.is_role_allowed(role):
        return ProjectionResult(status="disabled", disabled_reason="role_not_allowed")

    # 3. Load sidecar mapping
    board_map = load_board_epic_map(resolved_map_path)

    # 4. Provider mismatch protection (fail-closed before any adapter HTTP call)
    if board_map.provider and board_map.provider.strip().lower() != config.provider.strip().lower():
        raise ProviderMismatchError(
            f"Board projection provider mismatch: mapping is for '{board_map.provider}', "
            f"but current configuration requires '{config.provider}'. "
            f"Failing closed to prevent foreign ID dispatch."
        )

    # Ensure provider is recorded in map
    if not board_map.provider:
        board_map.provider = config.provider.strip().lower()

    # 5. Resolve adapter
    active_adapter = adapter
    if active_adapter is None:
        active_adapter = get_adapter(config)

    if active_adapter is None:
        return ProjectionResult(status="disabled", disabled_reason="provider_none")

    # Validate mappings on active provider (fail loudly on misconfigured stage/state map)
    if hasattr(active_adapter, "validate_mappings") and callable(getattr(active_adapter, "validate_mappings")):
        active_adapter.validate_mappings()

    # 6. Check existing card entry
    entry = board_map.epics.get(epic_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    if entry is None or not entry.external_id:
        # Lazy create card (typical first moment: finish after PLAN)
        card_title, card_description = resolve_card_fields(
            project_root=root_path,
            epic_id=epic_id,
            role=role,
            kind=kind,
            title=title,
            description=description,
        )
        epic_ref = EpicRef(
            epic_id=epic_id,
            title=card_title,
            description=card_description,
            phase=phase,
        )
        try:
            external_id = active_adapter.ensure_card(epic_ref)
            if not external_id:
                raise AdapterExecutionError(
                    f"Adapter {active_adapter.provider_name} returned empty external_id for epic {epic_id}"
                )
            board_map.epics[epic_id] = EpicMapEntry(
                external_id=external_id,
                last_phase=phase,
                sync_error=None,
                updated_at=now_iso,
            )
            save_board_epic_map(board_map, resolved_map_path)
            return ProjectionResult(status="success", external_id=external_id)
        except Exception as exc:
            # Soft-fail: log to stderr, write sync_error to sidecar, do not abort
            sys.stderr.write(f"Board projection soft-fail (ensure_card) for {epic_id}: {exc}\n")
            board_map.epics[epic_id] = EpicMapEntry(
                external_id=None,
                last_phase=phase,
                sync_error=str(exc),
                updated_at=now_iso,
            )
            save_board_epic_map(board_map, resolved_map_path)
            return ProjectionResult(status="soft_fail", error=str(exc))

    # Existing card -> move card
    external_id = entry.external_id
    # Idempotence check (BN-005)
    if entry.last_phase == phase and not entry.sync_error:
        return ProjectionResult(status="success", external_id=external_id)

    try:
        active_adapter.move_card(external_id, phase)
        entry.last_phase = phase
        entry.sync_error = None
        entry.updated_at = now_iso
        save_board_epic_map(board_map, resolved_map_path)
        return ProjectionResult(status="success", external_id=external_id)
    except Exception as exc:
        # Soft-fail
        sys.stderr.write(f"Board projection soft-fail (move_card) for {epic_id}: {exc}\n")
        entry.sync_error = str(exc)
        entry.updated_at = now_iso
        save_board_epic_map(board_map, resolved_map_path)
        return ProjectionResult(status="soft_fail", external_id=external_id, error=str(exc))


def project_after_transition(
    project_root: Path | str,
    epic_id: str,
    phase: str,
    role: str = "back",
    title: str = "",
    description: str = "",
    kind: str | None = None,
    config_path: Path | str | None = None,
    map_path: Path | str | None = None,
    adapter: BoardProjectionAdapter | None = None,
) -> ProjectionResult:
    """
    Convenience hook invoked after successful cursor commit on finish/halt (FR-004).
    Safe to call without raising exceptions (exceptions are logged and mapped to soft-fail).
    First finish after PLAN creates the card from prompt.md ## Board; later finishes move it.
    """
    try:
        return project_epic_phase(
            project_root=project_root,
            epic_id=epic_id,
            phase=phase,
            role=role,
            title=title,
            description=description,
            kind=kind,
            config_path=config_path,
            map_path=map_path,
            adapter=adapter,
        )
    except ProviderMismatchError:
        # Provider mismatch is a fatal misconfig that must raise or be surfaced explicitly
        raise
    except Exception as exc:
        sys.stderr.write(f"Board projection unexpected error: {exc}\n")
        return ProjectionResult(status="soft_fail", error=str(exc))


class BoardProjectionService:
    def __init__(
        self,
        project_root: Path | str,
        config_path: Path | str | None = None,
        map_path: Path | str | None = None,
        adapter: BoardProjectionAdapter | None = None,
    ) -> None:
        self.project_root = project_root
        self.config_path = config_path
        self.map_path = map_path
        self.adapter = adapter

    def project_epic_phase(
        self,
        epic_id: str,
        phase: str,
        role: str = "back",
        title: str = "",
        description: str = "",
        kind: str | None = None,
    ) -> ProjectionResult:
        return project_epic_phase(
            project_root=self.project_root,
            epic_id=epic_id,
            phase=phase,
            role=role,
            title=title,
            description=description,
            kind=kind,
            config_path=self.config_path,
            map_path=self.map_path,
            adapter=self.adapter,
        )

    def project_after_transition(
        self,
        epic_id: str,
        phase: str,
        role: str = "back",
        title: str = "",
        description: str = "",
        kind: str | None = None,
    ) -> ProjectionResult:
        return project_after_transition(
            project_root=self.project_root,
            epic_id=epic_id,
            phase=phase,
            role=role,
            title=title,
            description=description,
            kind=kind,
            config_path=self.config_path,
            map_path=self.map_path,
            adapter=self.adapter,
        )
