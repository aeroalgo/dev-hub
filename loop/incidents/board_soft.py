"""Soft-integration for T-HUB-015 board execution status updates on incident escalation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from loop.incidents.schema import IncidentRecord

logger = logging.getLogger(__name__)


def try_mark_board_execution_failed(
    incident: IncidentRecord,
    project_root: Path | str = "",
) -> bool:
    """Soft-integration helper to post failed execution metadata to T-HUB-015 board if DSH_MB_BRIDGE is present.

    Fail-soft: if DSH_MB_BRIDGE is present, calls its post_metadata/mark_failed hook.
    If bridge is missing or any exception occurs, logs a warning and returns False without raising.
    """
    try:
        # Dynamic feature-detect for DSH_MB_BRIDGE or 015 board plugin adapter
        import importlib

        try:
            bridge = importlib.import_module("dsh_mb_bridge")
        except ImportError:
            try:
                bridge = importlib.import_module("loop.board_sync.dsh_mb_bridge")
            except ImportError:
                # No bridge available — no-op fail-soft
                return False

        # If bridge module exists, invoke its board mark/metadata entry point if callable
        mark_fn = getattr(bridge, "mark_board_execution_failed", None) or getattr(
            bridge, "post_execution_failed", None
        )
        if callable(mark_fn):
            mark_fn(
                incident_id=incident.incident_id,
                epic_id=incident.epic_id,
                step_id=incident.step_id,
                project_root=str(project_root),
            )
            return True
        return False
    except Exception as exc:
        logger.warning("Soft board integration failed (fail-soft): %s", exc)
        return False
