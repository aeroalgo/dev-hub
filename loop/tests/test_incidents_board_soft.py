"""Unit tests for board_soft soft-integration helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import sys
import pytest

from loop.incidents.board_soft import try_mark_board_execution_failed
from loop.incidents.schema import IncidentRecord


def make_record(incident_id: str = "inc-100", status: str = "escalated") -> IncidentRecord:
    return IncidentRecord(
        schema="loop-incident/v1",
        incident_id=incident_id,
        status=status,
        opened_at="2026-08-30T12:00:00Z",
        project_root="/tmp/proj",
        epic_id="T-HUB-018",
        step_id="s09",
        phase="BACK IMPLEMENT",
        session_id="sess-1",
        source="check_after",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp-123",
    )


def test_board_soft_no_bridge_no_op():
    """Without DSH_MB_BRIDGE module, try_mark_board_execution_failed returns False without exception."""
    rec = make_record("inc-100")
    with patch.dict(sys.modules, {"dsh_mb_bridge": None, "loop.board_sync.dsh_mb_bridge": None}):
        res = try_mark_board_execution_failed(rec, project_root="/tmp/proj")
        assert res is False


def test_board_soft_bridge_posts_metadata():
    """With mock bridge present, try_mark_board_execution_failed invokes hook and returns True."""
    rec = make_record("inc-101")
    mock_bridge = MagicMock()
    mock_bridge.mark_board_execution_failed = MagicMock()

    with patch.dict(sys.modules, {"dsh_mb_bridge": mock_bridge}):
        res = try_mark_board_execution_failed(rec, project_root="/tmp/proj")
        assert res is True
        mock_bridge.mark_board_execution_failed.assert_called_once_with(
            incident_id="inc-101",
            epic_id="T-HUB-018",
            step_id="s09",
            project_root="/tmp/proj",
        )


def test_board_soft_bridge_exception_fail_soft():
    """When bridge call raises an exception, logs warning and returns False without failing."""
    rec = make_record("inc-102")
    mock_bridge = MagicMock()
    mock_bridge.mark_board_execution_failed.side_effect = RuntimeError("Bridge API down")

    with patch.dict(sys.modules, {"dsh_mb_bridge": mock_bridge}):
        res = try_mark_board_execution_failed(rec, project_root="/tmp/proj")
        assert res is False


def test_board_soft_no_secrets_in_payload():
    """Ensure metadata passed to board bridge does not leak sensitive environment data."""
    rec = make_record("inc-103")
    mock_bridge = MagicMock()

    with patch.dict(sys.modules, {"dsh_mb_bridge": mock_bridge}):
        try_mark_board_execution_failed(rec, project_root="/tmp/proj")
        args, kwargs = mock_bridge.mark_board_execution_failed.call_args
        assert kwargs["incident_id"] == "inc-103"
        assert kwargs["epic_id"] == "T-HUB-018"
        assert kwargs["step_id"] == "s09"
        assert "SECRET" not in str(kwargs)
