"""Tests for CheckpointRecord Pydantic schema and validate_checkpoint integration."""

import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

import pytest
from pydantic import ValidationError

from loop.schemas.checkpoint import (
    CHECKPOINT_ACTIONS,
    CHECKPOINT_RESUME_POLICIES,
    CHECKPOINT_STAGES,
    CHECKPOINT_STATUSES,
    CheckpointRecord,
)
from epic.core import validate_checkpoint, _CHECKPOINT_SCHEMA


def test_checkpoint_record_valid():
    record = CheckpointRecord(
        schema=_CHECKPOINT_SCHEMA,
        checkpoint_seq=1,
        checkpoint_id="cp1",
        session_id="sess-123",
        runner_id="runner-1",
        identity={"pipeline": "p1", "epic": "T-HUB-022", "role": "back", "step": "s04", "action": "run"},
        step_id="s04",
        phase="BACK IMPLEMENT",
        phase_epoch=1,
        projection_hash="abc123hash",
        stage="prepared",
        status="active",
        next_action="invoke",
        resume_policy="same_step",
        context_fingerprint="ctx-fp",
        index_fingerprint="idx-fp",
        retry_count=0,
        degraded_count=0,
        reason=None,
        metadata={"foo": "bar"},
        updated_at="2026-08-31T12:00:00Z",
    )
    assert record.checkpoint_seq == 1
    assert record.stage == "prepared"


def test_checkpoint_record_invalid_stage():
    with pytest.raises(ValidationError):
        CheckpointRecord(
            schema=_CHECKPOINT_SCHEMA,
            checkpoint_seq=1,
            checkpoint_id="cp1",
            session_id="sess-123",
            runner_id=None,
            identity={},
            step_id="s04",
            phase="BACK IMPLEMENT",
            phase_epoch=1,
            projection_hash=None,
            stage="invalid_stage",
            status="active",
            next_action="invoke",
            resume_policy="same_step",
        )


def test_validate_checkpoint_integration_valid():
    data = {
        "schema": _CHECKPOINT_SCHEMA,
        "checkpoint_seq": 1,
        "checkpoint_id": "cp1",
        "session_id": "sess-123",
        "runner_id": None,
        "identity": {"epic": "T-HUB-022"},
        "step_id": "s04",
        "phase": "BACK IMPLEMENT",
        "phase_epoch": 1,
        "projection_hash": "hash",
        "stage": "prepared",
        "status": "active",
        "next_action": "invoke",
        "resume_policy": "same_step",
        "context_fingerprint": None,
        "index_fingerprint": None,
        "retry_count": 0,
        "degraded_count": 0,
        "reason": None,
        "metadata": {},
        "updated_at": "2026-08-31T12:00:00Z",
    }
    valid, error = validate_checkpoint(data)
    assert valid is True
    assert error is None


def test_validate_checkpoint_missing_field():
    data = {
        "schema": _CHECKPOINT_SCHEMA,
        "checkpoint_seq": 1,
        # missing checkpoint_id
        "session_id": "sess-123",
        "step_id": "s04",
        "phase": "BACK IMPLEMENT",
        "phase_epoch": 1,
        "stage": "prepared",
        "status": "active",
        "next_action": "invoke",
        "resume_policy": "same_step",
    }
    valid, error = validate_checkpoint(data)
    assert valid is False
    assert error == "checkpoint_field_missing" or error == "checkpoint_schema_invalid"


def test_validate_checkpoint_wrong_status():
    data = {
        "schema": _CHECKPOINT_SCHEMA,
        "checkpoint_seq": 1,
        "checkpoint_id": "cp1",
        "session_id": "sess-123",
        "runner_id": None,
        "identity": {},
        "step_id": "s04",
        "phase": "BACK IMPLEMENT",
        "phase_epoch": 1,
        "projection_hash": None,
        "stage": "prepared",
        "status": "invalid_status",
        "next_action": "invoke",
        "resume_policy": "same_step",
    }
    valid, error = validate_checkpoint(data)
    assert valid is False
    assert "status" in str(error) or error == "checkpoint_status_invalid"
