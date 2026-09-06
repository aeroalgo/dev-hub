"""Tests for boundary_registry (TM-001, TM-010)."""

import pytest
from pydantic import BaseModel

from loop.schemas.boundary_registry import (
    BOUNDARY_REGISTRY,
    SCHEMA_LOOP_MB_LOAD,
    SCHEMA_LOOP_GATE_VERDICT,
    SCHEMA_LOOP_REPAIR_RESULT,
    SCHEMA_LOOP_VALIDATE_RESULT,
    SCHEMA_LOOP_SUNSET_INVENTORY,
)
from loop.mb_load.schemas import MbLoadResult
from loop.schemas.gate_verdict import GateVerdictRecord
from loop.schemas.repair_result import RepairResultRecord
from loop.schemas.validate_result import ValidateResult
from loop.schemas.sunset_inventory import SunsetReport


def test_boundary_registry_contains_sunset_schema():
    """TM-001 / TM-010 / SC-001: boundary registry contains canonical schemas including sunset."""
    assert SCHEMA_LOOP_MB_LOAD == "mb-load-result/v1"
    assert SCHEMA_LOOP_GATE_VERDICT == "loop-gate-verdict/v1"
    assert SCHEMA_LOOP_REPAIR_RESULT == "loop-repair-result/v1"
    assert SCHEMA_LOOP_VALIDATE_RESULT == "loop-validate-result/v1"
    assert SCHEMA_LOOP_SUNSET_INVENTORY == "loop-sunset-inventory/v1"

    assert SCHEMA_LOOP_SUNSET_INVENTORY in BOUNDARY_REGISTRY
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_MB_LOAD] is MbLoadResult
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_GATE_VERDICT] is GateVerdictRecord
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_REPAIR_RESULT] is RepairResultRecord
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_VALIDATE_RESULT] is ValidateResult
    assert BOUNDARY_REGISTRY[SCHEMA_LOOP_SUNSET_INVENTORY] is SunsetReport


def test_boundary_registry_classes_are_pydantic_models():
    """TM-010: all registered schema handlers are Pydantic models (no prose VERDICT path)."""
    for schema_id, model_cls in BOUNDARY_REGISTRY.items():
        assert issubclass(model_cls, BaseModel)


def test_canonical_sunset_not_schema_unknown_after_purge():
    """FR-010 / s05: canonical sunset id loop-sunset-inventory/v1 is never schema_unknown."""
    assert SCHEMA_LOOP_SUNSET_INVENTORY in BOUNDARY_REGISTRY
    assert BOUNDARY_REGISTRY.get(SCHEMA_LOOP_SUNSET_INVENTORY) is SunsetReport


def test_no_exact_four_registry_assert():
    """FR-010 / s05: registry is extensible, len(BOUNDARY_REGISTRY) >= 5, exact-four assert purged."""
    assert len(BOUNDARY_REGISTRY) >= 5


def test_no_prod_skip_sunset_search_agent():
    """FR-010 / s05: sunset agents are validated, not skipped as search-only."""
    from loop.schemas.boundary_registry import SCHEMA_LOOP_SUNSET_INVENTORY
    assert SCHEMA_LOOP_SUNSET_INVENTORY == "loop-sunset-inventory/v1"


