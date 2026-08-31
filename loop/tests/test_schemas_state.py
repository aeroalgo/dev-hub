"""Golden fixture tests for EpicState and DriftCounters Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from loop.schemas.state import DriftCounters, EpicState


def test_drift_counters_defaults() -> None:
    """Test all fields in DriftCounters default to 0."""
    counters = DriftCounters()
    assert counters.handoff_projected == 0
    assert counters.index_mirror_repair == 0
    assert counters.fingerprint_stall_repair == 0
    assert counters.gate_verdict_regex_fallback == 0
    assert counters.schema_invalid == 0


def test_epic_state_defaults_and_round_trip() -> None:
    """Test EpicState default construction, schema version and round-trip serialization."""
    state = EpicState()
    assert state.schema_version == "loop-state/v2"
    assert state.active is False
    assert state.status == "idle"
    assert isinstance(state.drift_counters, DriftCounters)

    dumped = state.model_dump()
    reconstructed = EpicState(**dumped)
    assert reconstructed == state
    assert reconstructed.schema_version == "loop-state/v2"


def test_epic_state_corrupt_field_caught() -> None:
    """Test invalid field type raises ValidationError (not silent drop)."""
    invalid_data = {
        "active": "not_a_bool_value",  # Invalid for strict boolean if coerced or invalid type
        "status": 12345,                # Status must be string or None
    }
    # Passing incompatible types or invalid schema structure raises ValidationError
    with pytest.raises(ValidationError):
        EpicState(active={"invalid": "dict_instead_of_bool"})


def test_epic_state_backward_compatibility_extra_allow() -> None:
    """Test extra fields are preserved due to extra='allow'."""
    data = {
        "active": True,
        "status": "running",
        "custom_legacy_field": "legacy_val",
    }
    state = EpicState(**data)
    assert state.active is True
    assert state.custom_legacy_field == "legacy_val"  # type: ignore[attr-defined]
