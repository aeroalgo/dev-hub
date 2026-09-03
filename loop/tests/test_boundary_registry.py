"""Tests for boundary_registry (TM-001, TM-010)."""

import pytest
from pydantic import BaseModel

from loop.schemas.boundary_registry import (
    BOUNDARY_REGISTRY,
    SCHEMA_LOOP_MB_LOAD,
    SCHEMA_LOOP_GATE_VERDICT,
    SCHEMA_LOOP_REPAIR_RESULT,
    SCHEMA_LOOP_VALIDATE_RESULT,
)
from loop.mb_load.schemas import MbLoadResult
from loop.schemas.gate_verdict import GateVerdictRecord
from loop.schemas.repair_result import RepairResultRecord
from loop.schemas.validate_result import ValidateResult


def test_boundary_registry_contains_all_four_schemas():
    """TM-001 / TM-010: boundary registry contains exact 4 canonical schemas."""
    assert SCHEMA_LOOP_MB_LOAD == "mb-load-result/v1"
    assert SCHEMA_LOOP_GATE_VERDICT == "loop-gate-verdict/v1"
    assert SCHEMA_LOOP_REPAIR_RESULT == "loop-repair-result/v1"
    assert SCHEMA_LOOP_VALIDATE_RESULT == "loop-validate-result/v1"

    assert len(BOUNDARY_REGISTRY) == 4
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_MB_LOAD] is MbLoadResult
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_GATE_VERDICT] is GateVerdictRecord
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_REPAIR_RESULT] is RepairResultRecord
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_VALIDATE_RESULT] is ValidateResult


def test_boundary_registry_classes_are_pydantic_models():
    """TM-010: all registered schema handlers are Pydantic models (no prose VERDICT path)."""
    for schema_id, model_cls in BOUNDARY_REGISTRY.items():
        assert issubclass(model_cls, BaseModel)

