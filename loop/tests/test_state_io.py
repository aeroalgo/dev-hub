"""Tests for load_epic_state, save_epic_state, _state_diagnostics, and increment_drift_counter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = str(ROOT / ".claude" / "hooks")
if HOOKS not in sys.path:
    sys.path.insert(0, HOOKS)

from epic_paths import state_path
from epic import (
    _state_diagnostics,
    default_state,
    increment_drift_counter,
    load_epic_state,
    save_epic_state,
)


def test_load_corrupt_json(tmp_path: Path) -> None:
    """Test corrupt JSON yields state_schema_invalid in diagnostics and safe default state."""
    sp = state_path(tmp_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{corrupt json", encoding="utf-8")

    diags = _state_diagnostics(tmp_path)
    assert "state_schema_invalid" in diags

    state = load_epic_state(tmp_path)
    assert state["active"] is False
    assert state["status"] == "idle"


def test_load_wrong_type_active(tmp_path: Path) -> None:
    """Test invalid field type yields state_schema_invalid diagnostic and safe default returned."""
    sp = state_path(tmp_path)
    sp.parent.mkdir(parents=True, exist_ok=True)
    invalid_data = {
        "active": {"invalid": "dict_instead_of_bool"},
        "status": "idle",
        "state_schema_version": "loop-state/v2",
    }
    sp.write_text(json.dumps(invalid_data), encoding="utf-8")

    diags = _state_diagnostics(tmp_path)
    assert "state_schema_invalid" in diags

    state = load_epic_state(tmp_path)
    assert state["active"] is False
    assert state["status"] == "idle"


def test_save_round_trip(tmp_path: Path) -> None:
    """Test save_epic_state serializes schema_version loop-state/v2 and drift_counters."""
    st = default_state()
    st["active"] = True
    st["status"] = "running"
    save_epic_state(tmp_path, st)

    sp = state_path(tmp_path)
    data = json.loads(sp.read_text(encoding="utf-8"))
    assert data["state_schema_version"] == "loop-state/v2"
    assert data["schema_version"] == "loop-state/v2"
    assert "drift_counters" in data
    assert data["drift_counters"]["handoff_projected"] == 0

    loaded = load_epic_state(tmp_path)
    assert loaded["active"] is True
    assert loaded["status"] == "running"
    assert loaded["drift_counters"]["handoff_projected"] == 0


def test_increment_drift_counter(tmp_path: Path) -> None:
    """Test increment_drift_counter increments counter across consecutive calls."""
    st = default_state()
    save_epic_state(tmp_path, st)

    increment_drift_counter(tmp_path, "handoff_projected")
    loaded = load_epic_state(tmp_path)
    assert loaded["drift_counters"]["handoff_projected"] == 1

    increment_drift_counter(tmp_path, "handoff_projected")
    loaded2 = load_epic_state(tmp_path)
    assert loaded2["drift_counters"]["handoff_projected"] == 2
