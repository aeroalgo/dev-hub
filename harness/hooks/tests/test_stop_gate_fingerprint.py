"""Tests for stop-gate last_finish_tool fingerprint and core.py wire."""

import json
import os
import subprocess
import sys
import unittest.mock
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "harness" / "hooks"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from harness.hooks.epic.core import (
    default_state,
    load_epic_state,
    save_epic_state,
    write_last_finish_tool,
    fingerprint_context,
)
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.schemas import (
    MbFinishRequest,
    LoopHandoffMeta,
    HandoffBody,
    LoadNowItem,
)


def test_fingerprint_write(tmp_path: Path):
    """cp1: write_last_finish_tool writes to epic state, load_epic_state returns the field."""
    st = load_epic_state(tmp_path)
    assert st.get("last_finish_tool") is None

    res = write_last_finish_tool(
        cwd=tmp_path,
        name="mb-finish implement",
        fingerprint="test-fp-12345",
    )
    assert res is True

    st_after = load_epic_state(tmp_path)
    lft = st_after.get("last_finish_tool")
    assert isinstance(lft, dict)
    assert lft.get("name") == "mb-finish implement"
    assert lft.get("fingerprint") == "test-fp-12345"
    assert "at" in lft


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_stop_gate_no_fingerprint(tmp_path: Path, monkeypatch):
    """cp2: stop-gate FINISH IMPLEMENT without fingerprint -> block (exit non-0 / block decision)."""
    ac_content = (
        "## load_now\n- [s02](path.yaml) — s02\n\n"
        "## Handoff BACK IMPLEMENT — in progress\n- status: in_progress\n"
    )
    _write_file(tmp_path / "memory-bank" / "activeContext.md", ac_content)

    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase": "IMPLEMENT",
            "mode": "implement",
            "last_verify_verdict": "PASS",
            "verify_done": True,
            "verify_verdict": "PASS",
            "pending_fingerprint_before": fingerprint_context(ac_content),
            "armed_step": "s02",
        }
    )
    save_epic_state(tmp_path, state)

    stop_gate_path = HOOKS / "stop-gate.py"
    cmd = [
        sys.executable,
        str(stop_gate_path),
    ]
    input_data = json.dumps(
        {
            "last_assistant_message": "FINISH s02",
            "cwd": str(tmp_path),
            "session_id": "test-session",
        }
    )
    res = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    out = res.stdout
    assert "block" in out
    assert "finish_tool_missing" in out


def test_finish_writes_fingerprint(tmp_path: Path):
    """cp3: finish_implement_step happy path after s02: fingerprint is written to epic state."""
    ac_content = (
        "## load_now\n- [s02](memory-bank/back/plan/decompose-test/s02.yaml) — s02\n\n"
        "## Handoff BACK IMPLEMENT — in progress\n- status: in_progress\n"
    )
    _write_file(tmp_path / "memory-bank" / "activeContext.md", ac_content)

    idx_content = (
        "schema: decompose-index/v1\n"
        "plan_id: decompose-test\n"
        "role: back\n"
        "next_phase: BACK IMPLEMENT\n"
        "steps:\n"
        "- id: s02\n"
        "  slug: s02\n"
        "  file: s02.yaml\n"
        "  title: s02\n"
        "  status: active\n"
    )
    _write_file(
        tmp_path / "memory-bank" / "back" / "plan" / "decompose-test" / "index.yaml",
        idx_content,
    )
    _write_file(
        tmp_path / "memory-bank" / "back" / "plan" / "decompose-test" / "s02.yaml",
        "schema: epic-decompose/v1\nstep_id: s02\n",
    )
    _write_file(
        tmp_path / "memory-bank" / "back" / "implement" / "implement-decompose-test" / "s02.yaml",
        "schema: epic-implement/v1\nstep_id: s02\nplan_id: decompose-test\ntitle: s02\ndate: '2026-09-01'\nstatus: in_progress\ndone:\n- s02 done\nfiles:\n- file.py\nintegration_check:\n- ok\ntests:\n- '`timeout 300s .venv/bin/pytest test.py`'\ncheckpoints:\n- id: cp1\n  criterion: cp1 done\n  status: done\n",
    )

    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase": "IMPLEMENT",
            "mode": "implement",
            "last_verify_verdict": "PASS",
            "verify_done": True,
            "verify_verdict": "PASS",
            "armed_step": "s02",
            "armed_decompose": "memory-bank/back/plan/decompose-test/s02.yaml",
        }
    )
    save_epic_state(tmp_path, state)

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s02",
        done_summary="finished s02 successfully",
        cwd=str(tmp_path),
    )

    with unittest.mock.patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify_check, \
         unittest.mock.patch("harness.hooks.epic.core._verify_pass_ready_for_step") as mock_verify_fin:
        mock_verify_check.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_verify_fin.return_value = {"ok": True, "diagnostic": "verify_pass"}

        res = finish_implement_step(req)
        assert res.ok is True, f"finish_implement_step failed: {res.diagnostic_codes} {res.shape_errors}"

    st_after = load_epic_state(tmp_path)
    lft = st_after.get("last_finish_tool")
    assert isinstance(lft, dict)
    assert lft.get("name") == "mb-finish implement"
    assert lft.get("fingerprint") is not None
