"""Unit tests for validate_boundary unified helper, schema-retry, and taxonomy (TM-003, TM-004, TM-011)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from loop.validate_boundary import validate_boundary
from loop.schemas.validate_result import ValidateResult
from _lib import (
    is_schema_error,
    is_semantic_error,
    get_schema_retry_count,
    increment_schema_retry_count,
)

ROOT = Path(__file__).resolve().parents[2]
EPIC_RESOLVE = ROOT / "harness" / "hooks" / "epic_resolve.py"
SUBAGENT_STOP = ROOT / "harness" / "hooks" / "subagent-stop.py"


def test_valid_gate_verdict_passes():
    """TM-004 / TM-011: valid gate verdict passes validation with empty error list."""
    payload = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify",
        "verdict": "PASS",
        "recorded_at": "2026-09-01T12:00:00Z",
    }
    res = validate_boundary("loop-gate-verdict/v1", payload)
    assert isinstance(res, ValidateResult)
    assert res.valid is True
    assert res.schema_id == "loop-gate-verdict/v1"
    assert res.errors == []
    assert res.diagnostic_codes == []


def test_invalid_gate_verdict_fails_with_errors():
    """TM-003: schema invalid payload yields valid=False and diagnostic code."""
    payload = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify",
    }
    res = validate_boundary("loop-gate-verdict/v1", payload)
    assert res.valid is False
    assert len(res.errors) > 0
    assert "schema_missing_verdict" in res.diagnostic_codes


def test_unknown_schema_id_fails():
    """TM-003: unknown schema_id yields fail-closed result."""
    res = validate_boundary("unknown-schema/v1", {})
    assert res.valid is False
    assert "schema_unknown_schema_id" in res.diagnostic_codes


def test_validate_boundary_sunset_zero_items_valid():
    """TM-002 / AC+1 / FR-006: semantic empty inventory is valid (zero items)."""
    payload = {
        "schema": "loop-sunset-inventory/v1",
        "boundary_id": "b_test_1",
        "new_sot": "loop.schemas.boundary_registry.BOUNDARY_REGISTRY",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [],
    }
    res = validate_boundary("loop-sunset-inventory/v1", payload)
    assert isinstance(res, ValidateResult)
    assert res.valid is True
    assert res.schema_id == "loop-sunset-inventory/v1"
    assert res.errors == []
    assert res.diagnostic_codes == []


def test_validate_boundary_sunset_nonzero_items_valid():
    """TM-006 / AC+2: non-zero items inventory passes validation."""
    payload = {
        "schema": "loop-sunset-inventory/v1",
        "boundary_id": "b_test_2",
        "new_sot": "loop.schemas.boundary_registry.BOUNDARY_REGISTRY",
        "forbidden_for_parent": ["old_helper"],
        "diagnostic_codes": [],
        "ok": True,
        "items": [
            {
                "kind": "A",
                "symbol": "old_func",
                "path": "loop/old_module.py",
                "start_line": 10,
                "end_line": 15,
                "excerpt": "def old_func():\n    pass",
                "mark": "REPLACE",
                "role": "back",
                "notes": "legacy stub",
            }
        ],
    }
    res = validate_boundary("loop-sunset-inventory/v1", payload)
    assert res.valid is True
    assert res.schema_id == "loop-sunset-inventory/v1"
    assert res.errors == []


def test_validate_boundary_sunset_extra_field_fails():
    """TM-003 / AC−5: extra field fails closed (extra=forbid)."""
    payload = {
        "schema": "loop-sunset-inventory/v1",
        "boundary_id": "b_test_3",
        "new_sot": "sot_target",
        "unexpected_extra_field": "disallowed",
        "items": [],
    }
    res = validate_boundary("loop-sunset-inventory/v1", payload)
    assert res.valid is False
    assert len(res.errors) > 0


def test_validate_boundary_canonical_sunset_not_schema_unknown():
    """US-004: canonical sunset id is recognized and does not produce schema_unknown_schema_id."""
    res = validate_boundary("loop-sunset-inventory/v1", {})
    assert "schema_unknown_schema_id" not in res.diagnostic_codes


def test_cli_sunset_validate_boundary():
    """SC-002 / AC+1: epic_resolve validate-boundary CLI with loop-sunset-inventory/v1."""
    valid_payload = json.dumps({
        "schema": "loop-sunset-inventory/v1",
        "boundary_id": "b_test_cli",
        "new_sot": "loop.schemas.boundary_registry.BOUNDARY_REGISTRY",
        "items": [],
    })
    proc = subprocess.run(
        [sys.executable, str(EPIC_RESOLVE), "validate-boundary", "--schema-id", "loop-sunset-inventory/v1", "--json", valid_payload],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data.get("valid") is True
    assert data.get("schema_id") == "loop-sunset-inventory/v1"


def test_invalid_json_string_fails():
    """TM-003: unparseable JSON string produces schema_json_decode_error."""
    res = validate_boundary("loop-gate-verdict/v1", "not json {")
    assert res.valid is False
    assert "schema_json_decode_error" in res.diagnostic_codes


def test_payload_not_dict_fails():
    """TM-003: non-dict JSON root produces schema_payload_not_dict."""
    res = validate_boundary("loop-gate-verdict/v1", json.dumps(["a", "b"]))
    assert res.valid is False
    assert "schema_payload_not_dict" in res.diagnostic_codes


def test_taxonomy_classifiers():
    """TM-011: is_schema_error vs is_semantic_error classification split."""
    assert is_schema_error(["schema_missing_verdict", "schema_invalid"]) is True
    assert is_schema_error(["semantic_ac_failed"]) is False
    assert is_schema_error([]) is False

    assert is_semantic_error(["semantic_ac_failed", "semantic_blocker"]) is True
    assert is_semantic_error(["schema_missing_verdict"]) is False
    assert is_semantic_error([]) is False


def test_schema_retry_counter_state(tmp_path: Path):
    from epic.core import save_epic_state
    save_epic_state(tmp_path, {})
    assert get_schema_retry_count(tmp_path, "tool_1") == 0
    assert increment_schema_retry_count(tmp_path, "tool_1") == 1
    assert increment_schema_retry_count(tmp_path, "tool_1") == 2
    assert get_schema_retry_count(tmp_path, "tool_1") == 2
    assert get_schema_retry_count(tmp_path, "tool_2") == 0


def test_epic_resolve_cli_validate_boundary(tmp_path: Path):
    valid_payload = json.dumps({
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify",
        "verdict": "PASS",
        "recorded_at": "2026-09-01T12:00:00Z",
    })
    proc = subprocess.run(
        [sys.executable, str(EPIC_RESOLVE), "validate-boundary", "--schema", "loop-gate-verdict/v1", "--json", valid_payload],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["valid"] is True

    invalid_payload = json.dumps({
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify",
    })
    proc_inv = subprocess.run(
        [sys.executable, str(EPIC_RESOLVE), "validate-boundary", "--schema", "loop-gate-verdict/v1", "--json", invalid_payload],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_inv.returncode == 1
    data_inv = json.loads(proc_inv.stdout)
    assert data_inv["valid"] is False


def test_tm003_tm004_subagent_stop_revalidates_and_retries(tmp_path: Path):
    from epic.core import save_epic_state
    save_epic_state(tmp_path, {})

    spawn_dir = tmp_path / ".claude" / "runtime" / "spawn-gate"
    spawn_dir.mkdir(parents=True, exist_ok=True)
    (spawn_dir / "sess-1.json").write_text(
        json.dumps({"need_verify": True, "verify_done": False}),
        encoding="utf-8",
    )

    bad_msg = (
        "Agent finished.\n"
        "```json\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify"}\n'
        "```\n"
    )

    # 1st attempt: retry 1 <= 2
    proc1 = subprocess.run(
        [sys.executable, str(SUBAGENT_STOP)],
        input=json.dumps({
            "session_id": "sess-1",
            "cwd": str(tmp_path),
            "agent_type": "verify",
            "last_assistant_message": bad_msg,
            "tool_use_id": "call_123",
        }),
        capture_output=True,
        text=True,
    )
    assert proc1.returncode == 2
    assert "schema validation failed" in proc1.stderr
    assert "retry 1/2" in proc1.stderr

    # 2nd attempt: retry 2 <= 2
    proc2 = subprocess.run(
        [sys.executable, str(SUBAGENT_STOP)],
        input=json.dumps({
            "session_id": "sess-1",
            "cwd": str(tmp_path),
            "agent_type": "verify",
            "last_assistant_message": bad_msg,
            "tool_use_id": "call_123",
        }),
        capture_output=True,
        text=True,
    )
    assert proc2.returncode == 2
    assert "retry 2/2" in proc2.stderr

    # 3rd attempt: retry 3 > 2 -> NEED_HUMAN escalation
    proc3 = subprocess.run(
        [sys.executable, str(SUBAGENT_STOP)],
        input=json.dumps({
            "session_id": "sess-1",
            "cwd": str(tmp_path),
            "agent_type": "verify",
            "last_assistant_message": bad_msg,
            "tool_use_id": "call_123",
        }),
        capture_output=True,
        text=True,
    )
    assert proc3.returncode == 2
    assert "NEED_HUMAN: schema_retry_exhausted:B-GATE" in proc3.stderr
