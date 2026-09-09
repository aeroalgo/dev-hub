"""Regression tests for the hard post-mb-finish tool barrier."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from harness.hooks.epic.core import default_state, save_epic_state


ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / "harness" / "hooks" / "finish-boundary-pretool.py"


def _run_hook(
    tmp_path: Path, *, tool_name: str = "Read", epic_loop: bool = True, runtime_id: str | None = None
) -> dict:
    payload = {
        "tool_name": tool_name,
        "cwd": str(tmp_path),
        "session_id": "claude-session",
    }
    if runtime_id:
        payload["runtime_id"] = runtime_id
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(tmp_path)
    env.pop("DEV_HUB", None)
    env.pop("HUB_ROOT", None)
    if epic_loop:
        env["EPIC_LOOP"] = "1"
    else:
        env.pop("EPIC_LOOP", None)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def _state(tmp_path: Path, *, phase_run_id: str, finish_run_id: str | None) -> None:
    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase_run_id": phase_run_id,
            "last_finish_tool": (
                {
                    "name": "mb-finish implement",
                    "fingerprint": "finish-fingerprint",
                    "phase_run_id": finish_run_id,
                }
                if finish_run_id is not None
                else None
            ),
        }
    )
    save_epic_state(tmp_path, state)


def test_successful_finish_denies_any_followup_tool(tmp_path: Path) -> None:
    _state(tmp_path, phase_run_id="run-1", finish_run_id="run-1")

    result = _run_hook(tmp_path, tool_name="Read")

    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "finish_boundary" in output["permissionDecisionReason"]
    assert "заверши текущий turn" in output["additionalContext"]


def test_successful_finish_uses_codex_block_envelope(tmp_path: Path) -> None:
    _state(tmp_path, phase_run_id="run-1", finish_run_id="run-1")

    result = _run_hook(tmp_path, tool_name="Bash", runtime_id="codex")

    assert result["decision"] == "block"
    assert "finish_boundary" in result["reason"]


def test_new_phase_run_is_unblocked_after_finish(tmp_path: Path) -> None:
    _state(tmp_path, phase_run_id="run-2", finish_run_id="run-1")

    assert _run_hook(tmp_path, tool_name="Read") == {}


def test_failed_or_missing_finish_does_not_activate_barrier(tmp_path: Path) -> None:
    _state(tmp_path, phase_run_id="run-1", finish_run_id=None)

    assert _run_hook(tmp_path, tool_name="Bash") == {}


def test_barrier_is_scoped_to_epic_loop(tmp_path: Path) -> None:
    _state(tmp_path, phase_run_id="run-1", finish_run_id="run-1")

    assert _run_hook(tmp_path, tool_name="Read", epic_loop=False) == {}
