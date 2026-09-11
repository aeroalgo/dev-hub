"""Tests for agent tool boundary write protections on runtime gate, spawn-gate, and verifier state.

FR-003, AC+3, TM-077-01:
- Deny Write/Edit to runtime gate files (.claude/runtime/spawn-gate/**, .claude/runtime/epic/**, .claude/runtime/gate/**)
- Deny Bash commands attempting to write, edit, rm, or truncate runtime gate files
- Diagnostic is observable and fail-closed
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WRITE_PRETOOL = ROOT / ".claude" / "hooks" / "pretool-dispatch.py"
BASH_PRETOOL = ROOT / ".claude" / "hooks" / "pretool-dispatch.py"
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from _lib import (
    gate_state_write_deny_reason,
    bash_gate_state_write_deny_reason,
)


def _run_write_pretool(cwd: Path, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(WRITE_PRETOOL)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def _run_bash_pretool(cwd: Path, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(BASH_PRETOOL)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def test_write_pretool_denies_direct_write_to_spawn_gate_runtime(tmp_path: Path):
    target = tmp_path / ".claude" / "runtime" / "spawn-gate" / "test-session.json"
    res = _run_write_pretool(
        tmp_path,
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "contents": json.dumps({"verify_verdict": "PASS"}),
            },
            "cwd": str(tmp_path),
        },
    )
    out = res.get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"
    assert "runtime_gate_write_forbidden" in out.get("permissionDecisionReason", "")


def test_write_pretool_denies_edit_to_epic_runtime_state(tmp_path: Path):
    target = tmp_path / ".claude" / "runtime" / "epic" / "state.json"
    res = _run_write_pretool(
        tmp_path,
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "FAIL",
                "new_string": "PASS",
            },
            "cwd": str(tmp_path),
        },
    )
    out = res.get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"
    assert "runtime_gate_write_forbidden" in out.get("permissionDecisionReason", "")


def test_bash_pretool_denies_shell_write_to_runtime_gate_files(tmp_path: Path):
    dangerous_cmds = [
        "echo '{\"verify_verdict\": \"PASS\"}' > .claude/runtime/spawn-gate/sess.json",
        "cat << 'EOF' > .claude/runtime/epic/state.json\n{\"last_verify_verdict\":\"PASS\"}\nEOF",
        "sed -i 's/FAIL/PASS/' .claude/runtime/spawn-gate/sess.json",
        "rm -f .claude/runtime/spawn-gate/*.json",
        "truncate -s 0 .claude/runtime/epic/state.json",
        "tee .claude/runtime/gate_verdicts.jsonl <<< 'PASS'",
    ]
    for cmd in dangerous_cmds:
        res = _run_bash_pretool(
            tmp_path,
            {
                "tool_name": "Bash",
                "tool_input": {"command": cmd},
                "cwd": str(tmp_path),
            },
        )
        out = res.get("hookSpecificOutput", {})
        assert out.get("permissionDecision") == "deny", f"Command was not denied: {cmd}"
        assert "runtime_gate_write_forbidden" in out.get("permissionDecisionReason", "")
