"""Tests for Step s04: Kind I — prompt schema_id = registry, 08-row sunset wired."""

from __future__ import annotations

import json
from pathlib import Path
import re
import pytest
from pydantic import ValidationError

from loop.schemas.boundary_registry import BOUNDARY_REGISTRY, SCHEMA_LOOP_SUNSET_INVENTORY
from loop.schemas.sunset_inventory import SunsetReport
from loop.sunset_sidecar_store import write_sunset_sidecar, read_sunset_sidecar


def _read_prompt_text() -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "harness" / "agents" / "sunset-inventory.md"
    assert prompt_path.is_file(), f"Missing sunset prompt file at {prompt_path}"
    return prompt_path.read_text(encoding="utf-8")


def test_sunset_agent_prompt_schema_id_matches_registry():
    """FR-007: Prompt schema_id equals SCHEMA_LOOP_SUNSET_INVENTORY from registry."""
    prompt_text = _read_prompt_text()
    assert SCHEMA_LOOP_SUNSET_INVENTORY in prompt_text, (
        f"Prompt must explicitly reference constant string {SCHEMA_LOOP_SUNSET_INVENTORY}"
    )

    # Check that the json template inside the prompt markdown uses SCHEMA_LOOP_SUNSET_INVENTORY
    m = re.search(r"```json\s*(\{.*?\})\s*```", prompt_text, re.DOTALL)
    assert m is not None, "Prompt must contain a fenced ```json block"
    raw_json_str = m.group(1)
    assert f'"schema": "{SCHEMA_LOOP_SUNSET_INVENTORY}"' in raw_json_str


def test_sunset_prompt_retains_machine_contract():
    """FR-010: Prompt still contains loop-sunset-inventory/v1 fence contract (no prose-only downgrade)."""
    prompt_text = _read_prompt_text()
    assert "loop-sunset-inventory/v1" in prompt_text
    assert "schema" in prompt_text
    assert "items" in prompt_text
    assert "mark" in prompt_text
    assert "excerpt" in prompt_text
    assert "REPLACE" in prompt_text


def test_sunset_matrix_row_stop_parse_schema_sidecar(tmp_path: Path):
    """FR-008 / SC-004: Living 08-style row assertion for sunset-inventory.

    Living matrix row:
    - Agent / Gate: sunset-inventory
    - Start inject: yes (agent markdown exists with loop-sunset-inventory/v1 schema fence)
    - Stop parse: yes (SubagentStop parses fenced JSON with registered schema)
    - Schema: sunset (SCHEMA_LOOP_SUNSET_INVENTORY)
    - Sidecar: yes (persisted as SunsetReport in runtime directory)
    """
    # 1. Registry lookup
    schema_cls = BOUNDARY_REGISTRY.get(SCHEMA_LOOP_SUNSET_INVENTORY)
    assert schema_cls is SunsetReport

    # 2. Valid payload passes boundary validation
    payload = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "b1",
        "new_sot": "sot1",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [
            {
                "kind": "A",
                "symbol": "old_func",
                "path": "app/old.py",
                "start_line": 1,
                "end_line": 5,
                "excerpt": "def old_func():\n    pass",
                "mark": "REPLACE",
                "role": "back",
            }
        ],
    }
    validated = schema_cls.model_validate(payload)
    assert isinstance(validated, SunsetReport)

    # 3. Sidecar write + read round-trip
    session_id = "test-matrix-session"
    step_id = "s04"
    written = write_sunset_sidecar(tmp_path, session_id, validated, step_id=step_id)
    assert written.boundary_id == "b1"

    read_back = read_sunset_sidecar(tmp_path, session_id, step_id=step_id)
    assert read_back is not None
    assert read_back.boundary_id == "b1"
    assert len(read_back.items) == 1
    assert read_back.items[0].symbol == "old_func"


def test_wrong_schema_id_in_prompt_fails_validate():
    """AC-3 / Misconfig: Wrong schema id in prompt/fixture fails validation, no prose accept."""
    # Unknown schema lookup in registry returns None
    assert BOUNDARY_REGISTRY.get("wrong-schema-id/v1") is None

    # SunsetReport with wrong schema string fails validation
    invalid_schema_payload = {
        "schema": "wrong-schema-id/v1",
        "boundary_id": "b1",
        "new_sot": "sot1",
        "ok": True,
        "items": [],
    }
    with pytest.raises(ValidationError):
        SunsetReport.model_validate(invalid_schema_payload)
