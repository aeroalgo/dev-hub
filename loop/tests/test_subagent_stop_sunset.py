"""Tests for SubagentStop handling of sunset-inventory agent."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from loop.schemas.boundary_registry import SCHEMA_LOOP_SUNSET_INVENTORY
from loop.schemas.sunset_inventory import SunsetReport
from loop.sunset_sidecar_store import read_sunset_sidecar, sunset_sidecar_path


def _run_subagent_stop(stdin_data: dict, cwd: Path) -> subprocess.CompletedProcess[str]:
    hook_path = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "subagent-stop.py"
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(stdin_data),
        text=True,
        capture_output=True,
        cwd=str(cwd),
    )


def test_sunset_stop_writes_sidecar_with_schema_id_persist(tmp_path: Path):
    """TM-005 / US-003 / cp1: Valid sunset fence on sunset-inventory stop validates sunset schema and persists sidecar."""
    payload = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "sunset-stop-pipeline",
        "new_sot": "harness/hooks/subagent-stop.py#sunset-inventory",
        "forbidden_for_parent": ["no unvalidated transcript"],
        "diagnostic_codes": [],
        "ok": True,
        "items": [
            {
                "kind": "A",
                "symbol": "main",
                "path": "harness/hooks/subagent-stop.py",
                "start_line": 303,
                "end_line": 306,
                "excerpt": "clear_in_flight",
                "mark": "REPLACE",
                "role": "back",
                "notes": "Wire sunset stop branch",
            }
        ],
    }
    transcript = f"Here is the sunset inventory:\n```json\n{json.dumps(payload)}\n```\nDone."
    data = {
        "agent_type": "sunset-inventory",
        "message": transcript,
        "session_id": "test-sess-sunset-valid",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 0
    assert "schema validation failed" not in res.stderr
    assert "NEED_HUMAN" not in res.stderr

    # TM-005 / cp1 / cp2: Sidecar exists and contains valid schema
    report = read_sunset_sidecar(tmp_path, "test-sess-sunset-valid")
    assert report is not None
    assert report.schema_version == SCHEMA_LOOP_SUNSET_INVENTORY
    assert report.boundary_id == "sunset-stop-pipeline"
    assert report.ok is True


def test_subagent_stop_sunset_alias_sunset_same_branch(tmp_path: Path):
    """alias sunset runs through the exact same branch."""
    payload = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "sunset-stop-pipeline",
        "new_sot": "harness/hooks/subagent-stop.py#sunset-inventory",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [],
    }
    transcript = f"```json\n{json.dumps(payload)}\n```"
    data = {
        "agent_type": "sunset",
        "message": transcript,
        "session_id": "test-sess-sunset-alias",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 0
    assert "schema validation failed" not in res.stderr


def test_subagent_stop_sunset_no_fence_not_success(tmp_path: Path):
    """TM-004 / US-002 / cp2: No-fence transcript is not success, triggers retry or block."""
    data = {
        "agent_type": "sunset-inventory",
        "message": "I found nothing and here is my summary text without any json fence.",
        "session_id": "test-sess-sunset-nofence",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 2
    assert "sunset-inventory: schema validation failed" in res.stderr
    assert "MUST re-emit valid loop-sunset-inventory/v1 JSON fence" in res.stderr


def test_subagent_stop_sunset_schema_retry_then_need_human(tmp_path: Path):
    """FR-006 / cp3: Malformed fence retries once (retry 1/1) then triggers NEED_HUMAN on second failure."""
    invalid_data = {
        "agent_type": "sunset-inventory",
        "message": "```json\n{\"schema\": \"loop-sunset-inventory/v1\", \"invalid_field\": 123}\n```",
        "session_id": "test-sess-sunset-retry",
        "cwd": str(tmp_path),
    }
    # First attempt: retry 1/1
    res1 = _run_subagent_stop(invalid_data, tmp_path)
    assert res1.returncode == 2
    assert "MUST re-emit valid loop-sunset-inventory/v1 JSON fence (retry 1/1)" in res1.stderr

    # Second attempt: exhausted -> NEED_HUMAN
    res2 = _run_subagent_stop(invalid_data, tmp_path)
    assert res2.returncode == 2
    assert "NEED_HUMAN: schema_retry_exhausted:B-SUNSET" in res2.stderr


def test_subagent_stop_sunset_not_validated_as_gate_schema(tmp_path: Path):
    """TM-006 / cp4: Sunset transcript must not be validated as loop-gate-verdict/v1."""
    # Gate verdict payload should fail validation under sunset schema
    gate_payload = {
        "schema": "loop-gate-verdict/v1",
        "verdict": "PASS",
        "summary": "all good",
    }
    data = {
        "agent_type": "sunset-inventory",
        "message": f"```json\n{json.dumps(gate_payload)}\n```",
        "session_id": "test-sess-sunset-not-gate",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 2
    assert "sunset-inventory: schema validation failed" in res.stderr


def test_parent_reads_sunset_sidecar(tmp_path: Path):
    """FR-005 / US-003: Parent helper reads sidecar with schema_id."""
    payload = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "test-boundary",
        "new_sot": "test-sot",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [],
    }
    data = {
        "agent_type": "sunset-inventory",
        "message": f"```json\n{json.dumps(payload)}\n```",
        "session_id": "test-sess-parent-read",
        "step_id": "s03",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 0

    report = read_sunset_sidecar(tmp_path, "test-sess-parent-read", step_id="s03")
    assert report is not None
    assert report.schema_version == SCHEMA_LOOP_SUNSET_INVENTORY
    assert report.boundary_id == "test-boundary"
    assert report.new_sot == "test-sot"
    assert report.ok is True


def test_sunset_persist_io_error_need_human_persist_fail(tmp_path: Path):
    """cp3 / Plan C: Persist IO failure fail-closed triggers NEED_HUMAN and returncode=2."""
    payload = {
        "schema": SCHEMA_LOOP_SUNSET_INVENTORY,
        "boundary_id": "test-boundary",
        "new_sot": "test-sot",
        "forbidden_for_parent": [],
        "diagnostic_codes": [],
        "ok": True,
        "items": [],
    }
    # Create sidecar destination path as a directory to force OSError on write
    target_sidecar = sunset_sidecar_path(tmp_path, "test-sess-persist-fail")
    target_sidecar.parent.mkdir(parents=True, exist_ok=True)
    target_tmp = target_sidecar.with_suffix(".json.tmp")
    target_tmp.mkdir(parents=True, exist_ok=True)  # Causes open/write to fail with IsADirectoryError / PermissionError

    data = {
        "agent_type": "sunset-inventory",
        "message": f"```json\n{json.dumps(payload)}\n```",
        "session_id": "test-sess-persist-fail",
        "cwd": str(tmp_path),
    }
    res = _run_subagent_stop(data, tmp_path)
    assert res.returncode == 2
    assert "NEED_HUMAN: sunset_sidecar_persist_failed" in res.stderr


def test_no_fence_does_not_write_ok_sidecar(tmp_path: Path):
    """Regression: no fence does not create sidecar file."""
    data = {
        "agent_type": "sunset-inventory",
        "message": "No fence here",
        "session_id": "test-sess-nofence-sidecar",
        "cwd": str(tmp_path),
    }
    _run_subagent_stop(data, tmp_path)
    assert read_sunset_sidecar(tmp_path, "test-sess-nofence-sidecar") is None

