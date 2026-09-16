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
    execution_evidence_write_deny_reason,
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


def test_runtime_gate_write_pretool_denies_direct_write_to_spawn_gate_runtime(tmp_path: Path):
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


def test_runtime_gate_write_pretool_denies_edit_to_epic_runtime_state(tmp_path: Path):
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


def test_runtime_gate_bash_pretool_denies_shell_write_to_runtime_gate_files(tmp_path: Path):
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


# Backward-compatible aliases for legacy test selectors
test_write_pretool_denies_direct_write_to_spawn_gate_runtime = test_runtime_gate_write_pretool_denies_direct_write_to_spawn_gate_runtime
test_write_pretool_denies_edit_to_epic_runtime_state = test_runtime_gate_write_pretool_denies_edit_to_epic_runtime_state
test_bash_pretool_denies_shell_write_to_runtime_gate_files = test_runtime_gate_bash_pretool_denies_shell_write_to_runtime_gate_files


def test_receipt_executor_write_path_and_verifier_receipt_remain_intact():
    """CP3: Positive baseline verifying that legitimate verifier receipts and executor paths remain valid."""
    from _lib import verdict_evidence
    identity = {
        "session_id": "session-test",
        "epic_id": "T-HUB-099",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-test",
        "phase_epoch": "epoch-test",
        "event_digest": "digest-test",
        "authority": "autonomous",
    }
    evidence = verdict_evidence(identity, "PASS", verifier_identity="verify-implement")
    assert evidence["schema"] == "loop-verifier-receipt/v1"
    assert evidence["authority"] == "autonomous"


@pytest.mark.parametrize("role", ["back", "front", "integration"])
def test_write_execution_evidence_denied_for_all_roles(tmp_path: Path, role: str):
    target = (
        tmp_path
        / "memory-bank"
        / role
        / "execution"
        / "T-HUB-099"
        / "s01"
        / "capability-deadbeef.json"
    )
    res = _run_write_pretool(
        tmp_path,
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "contents": json.dumps({"status": "succeeded"}),
            },
            "cwd": str(tmp_path),
        },
    )
    out = res.get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"
    assert "execution_evidence_write_forbidden" in out.get(
        "permissionDecisionReason", ""
    )


@pytest.mark.parametrize("role", ["back", "front", "integration"])
def test_edit_execution_evidence_denied_for_all_roles(tmp_path: Path, role: str):
    target = (
        tmp_path
        / "memory-bank"
        / role
        / "execution"
        / "T-HUB-099"
        / "s01"
        / "capability-deadbeef.json"
    )
    res = _run_write_pretool(
        tmp_path,
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "failed",
                "new_string": "succeeded",
            },
            "cwd": str(tmp_path),
        },
    )
    out = res.get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"
    assert "execution_evidence_write_forbidden" in out.get(
        "permissionDecisionReason", ""
    )


def test_bash_pretool_denies_shell_write_to_execution_evidence(tmp_path: Path):
    dangerous_cmds = [
        "echo '{\"status\": \"succeeded\"}' > memory-bank/back/execution/T-APP-001/s01/capability-1234.json",
        "sed -i 's/failed/succeeded/' memory-bank/integration/execution/T-APP-001/s01/capability-1234.json",
        "rm -f memory-bank/back/execution/T-APP-001/s01/capability-1234.json",
        "truncate -s 0 memory-bank/back/execution/T-APP-001/s01/capability-1234.json",
        "tee memory-bank/back/execution/T-APP-001/s01/capability-1234.json <<< 'data'",
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
        assert "execution_evidence_write_forbidden" in out.get(
            "permissionDecisionReason", ""
        )


@pytest.mark.parametrize("role", ["back", "front", "integration"])
def test_execution_evidence_write_deny_reason(role: str, tmp_path: Path):
    path = f"memory-bank/{role}/execution/T-HUB-099/s01/capability-1234abcd.json"
    reason = execution_evidence_write_deny_reason(tmp_path, path)
    assert reason is not None
    assert "execution_evidence_write_denied" in reason
    assert "execution_evidence_write_forbidden" in reason

    # Path traversal outside project root returns None safely
    assert execution_evidence_write_deny_reason(tmp_path, "/tmp/other/capability-1234.json") is None
    assert execution_evidence_write_deny_reason(tmp_path, "../../outside/capability-1234.json") is None

    # Non-execution paths return None
    assert execution_evidence_write_deny_reason(tmp_path, "loop/context_loop.py") is None
    assert execution_evidence_write_deny_reason(tmp_path, "memory-bank/back/plan/T-HUB-099/yaml/steps/s01.yaml") is None
