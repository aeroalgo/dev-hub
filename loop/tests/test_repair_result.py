"""Tests for loop-repair-result/v1 schema and invariants (FR-006, US-004, SC-004, TM-004)."""

import pytest
from pydantic import ValidationError

from loop.schemas.repair_result import RepairResultRecord, SCHEMA_LOOP_REPAIR_RESULT
from loop.validate_boundary import validate_boundary


def test_repair_result_valid_minimal() -> None:
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "done",
        "fixed_blockers": ["b1", "b2"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    rec = RepairResultRecord.model_validate(data)
    assert rec.parent_evidence_id == "evidence-fail-123"
    assert rec.agent_id == "gate-repair"
    assert rec.status == "done"
    assert rec.fixed_blockers == ["b1", "b2"]
    assert rec.remaining_blockers == []


def test_repair_done_with_remaining_invalid() -> None:
    """done requires empty remaining (QA TM-004 / SC-004 / AC-5)."""
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "done",
        "fixed_blockers": ["b1"],
        "remaining_blockers": ["b2"],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    with pytest.raises(ValidationError, match="requires empty remaining"):
        RepairResultRecord.model_validate(data)


def test_repair_disjoint_fixed_and_remaining() -> None:
    """remaining and fixed must be disjoint."""
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "partial",
        "fixed_blockers": ["b1", "b2"],
        "remaining_blockers": ["b2", "b3"],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    with pytest.raises(ValidationError, match="disjoint"):
        RepairResultRecord.model_validate(data)


def test_repair_parent_evidence_required() -> None:
    """parent_evidence_id is required on wire (FR-006 / US-004)."""
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "status": "done",
        "fixed_blockers": ["b1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    with pytest.raises(ValidationError):
        RepairResultRecord.model_validate(data)


def test_repair_agent_id_gate_repair_only() -> None:
    """agent_id must be gate-repair."""
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "other-agent",
        "status": "done",
        "fixed_blockers": ["b1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    with pytest.raises(ValidationError, match="gate-repair"):
        RepairResultRecord.model_validate(data)


def test_repair_fail_requires_remaining_or_diagnostic() -> None:
    """status=fail requires remaining_blockers or diagnostic."""
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "fail",
        "fixed_blockers": [],
        "remaining_blockers": [],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    with pytest.raises(ValidationError, match="fail.*remaining.*diagnostic"):
        RepairResultRecord.model_validate(data)

    data_ok = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "fail",
        "fixed_blockers": [],
        "remaining_blockers": ["b1"],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    rec = RepairResultRecord.model_validate(data_ok)
    assert rec.status == "fail"

    data_diagnostic_ok = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "fail",
        "fixed_blockers": [],
        "remaining_blockers": [],
        "diagnostic": "cannot resolve syntax error in external lib",
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    rec2 = RepairResultRecord.model_validate(data_diagnostic_ok)
    assert rec2.diagnostic == "cannot resolve syntax error in external lib"


def test_validate_boundary_repair_result() -> None:
    data = {
        "schema": SCHEMA_LOOP_REPAIR_RESULT,
        "parent_evidence_id": "evidence-fail-123",
        "agent_id": "gate-repair",
        "status": "done",
        "fixed_blockers": ["b1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    res = validate_boundary(SCHEMA_LOOP_REPAIR_RESULT, data)
    assert res.valid is True

    # Invalid: done with leftover
    data_bad = dict(data, remaining_blockers=["b2"])
    res_bad = validate_boundary(SCHEMA_LOOP_REPAIR_RESULT, data_bad)
    assert res_bad.valid is False
