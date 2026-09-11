"""Parity and functional test suite for canonical PreToolUse dispatcher and policies.

Covers:
- CP1: Agent/Task pretool checks, model overrides, prompt validation, and agent isolation parity.
- CP2: Bash and Write pretool checks, unmanaged test execution blocking, and protected files.
- CP3: Finish and project boundary precedence, short-circuit on deny across all tool types.
- CP4: End-to-end dispatcher execution with envelope formatting and fail-closed handling.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

try:
    from hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PreToolUse,
        dispatch_pretool,
    )
except ImportError:
    from harness.hooks.hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PreToolUse,
        dispatch_pretool,
    )

from pretool_policy import (
    AgentPolicyAdapter,
    BashPolicyAdapter,
    FinishBoundaryAdapter,
    ProjectBoundaryAdapter,
    WritePolicyAdapter,
    create_pretool_branches,
    dispatch_pretool_event,
)
from harness.hooks.epic.core import default_state, save_epic_state


DISPATCHER_CLI = HOOKS / "pretool-dispatch.py"


def _run_cli(payload: dict[str, Any], env_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(DISPATCHER_CLI)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"Dispatcher failed with stderr: {proc.stderr}"
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


# ============================================================================
# CP1 / TDD: Agent & Task Pretool Policy Parity
# ============================================================================

def test_pretool_agent_policy_parity(tmp_path: Path) -> None:
    """Parity test: Agent/Task prompt validation and normalizer enforce identical deny/allow."""
    adapter = AgentPolicyAdapter()

    from _lib import save_state
    save_state("test-session-agent", str(ROOT), {
        "active": True,
        "mode": "IMPLEMENT",
        "workflow_active": True,
        "session_id": "test-session-agent",
        "gate_identity": {
            "session_id": "test-session-agent",
            "epic_id": "T-HUB-085",
            "step_id": "s03",
        },
    })

    ctx_valid = EventContext(
        event_name=PreToolUse,
        tool_name="Agent",
        tool_input={
            "subagent_type": "verify-implement",
            "prompt": "GATE_IDENTITY session_id=test-session-agent epic_id=T-HUB-085 step_id=s03\nVerify this step",
        },
        cwd=ROOT,
        session_id="test-session-agent",
        raw_payload={
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "verify-implement",
                "prompt": "GATE_IDENTITY session_id=test-session-agent epic_id=T-HUB-085 step_id=s03\nVerify this step",
            },
            "cwd": str(ROOT),
            "session_id": "test-session-agent",
        },
    )
    res_valid = adapter.evaluate(ctx_valid)
    assert res_valid is not None
    assert res_valid.is_allow
    assert res_valid.updated_input is not None
    assert res_valid.updated_input.get("subagent_type") == "verify-implement"


def test_agent_task_model_override_and_updated_input(tmp_path: Path) -> None:
    """Agent and Task tool invocations normalize subagent_type and update input."""
    adapter = AgentPolicyAdapter()
    from _lib import save_state
    save_state("test-session-agent", str(ROOT), {"active": True, "mode": "IMPLEMENT", "workflow_active": True})

    valid_prompt = (
        "agent_type: worker\n"
        "GATE_IDENTITY session_id=test-session-agent epic_id=T-HUB-085 step_id=s03\n"
        "Do unit testing."
    )
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Task",
        tool_input={
            "agent_type": "worker",
            "prompt": valid_prompt,
        },
        cwd=ROOT,
        session_id="test-session-agent",
        raw_payload={
            "tool_name": "Task",
            "tool_input": {
                "agent_type": "worker",
                "prompt": valid_prompt,
            },
            "cwd": str(ROOT),
            "session_id": "test-session-agent",
        },
    )
    res = adapter.evaluate(ctx)
    assert res is not None
    assert res.is_allow
    assert res.updated_input is not None
    assert res.updated_input.get("subagent_type") == "worker"


def test_agent_policy_routes_read_tools_to_context_ledger(tmp_path: Path) -> None:
    """Read tool aliases are routed to context ledger through AgentPolicyAdapter."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("print('hello world')\n", encoding="utf-8")

    adapter = AgentPolicyAdapter()
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Read",
        tool_input={"file_path": str(test_file)},
        cwd=tmp_path,
        session_id="test-read-sess",
        raw_payload={
            "tool_name": "Read",
            "tool_input": {"file_path": str(test_file)},
            "cwd": str(tmp_path),
            "session_id": "test-read-sess",
        },
    )
    res = adapter.evaluate(ctx)
    assert res is not None
    assert res.is_allow
    assert "additionalContext" in res.metadata or "additional_context" in res.metadata


# ============================================================================
# CP2 / TDD: Bash & Write Policy Parity
# ============================================================================

def test_pretool_bash_policy_parity(tmp_path: Path) -> None:
    """Parity test: BashPolicyAdapter denies writes to runtime gate files and runner-owned CLI."""
    adapter = BashPolicyAdapter()

    # 1. Gate state overwrite attempt
    ctx_gate = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "echo '{\"verdict\":\"PASS\"}' > .claude/runtime/spawn-gate/sess.json"},
        cwd=tmp_path,
    )
    res_gate = adapter.evaluate(ctx_gate)
    assert res_gate is not None
    assert res_gate.is_deny
    assert "runtime_gate_write_forbidden" in str(res_gate.reason)

    # 2. Runner CLI forbidden attempt in epic loop
    ctx_runner = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "python3 .claude/hooks/epic_resolve.py halt"},
        cwd=tmp_path,
    )
    old_loop = os.environ.get("EPIC_LOOP")
    os.environ["EPIC_LOOP"] = "1"
    try:
        res_runner = adapter.evaluate(ctx_runner)
        assert res_runner is not None
        assert res_runner.is_deny
        assert "runner_cli_forbidden" in str(res_runner.reason)
    finally:
        if old_loop is not None:
            os.environ["EPIC_LOOP"] = old_loop
        else:
            os.environ.pop("EPIC_LOOP", None)


def test_pretool_write_policy_parity(tmp_path: Path) -> None:
    """Parity test: WritePolicyAdapter denies overwrite of activeContext and runtime state."""
    adapter = WritePolicyAdapter()

    # 1. Direct write to .claude/runtime
    ctx_runtime = EventContext(
        event_name=PreToolUse,
        tool_name="Write",
        tool_input={
            "file_path": str(tmp_path / ".claude" / "runtime" / "spawn-gate" / "foo.json"),
            "contents": "{}",
        },
        cwd=tmp_path,
        raw_payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / ".claude" / "runtime" / "spawn-gate" / "foo.json"),
                "contents": "{}",
            },
            "cwd": str(tmp_path),
        },
    )
    res_runtime = adapter.evaluate(ctx_runtime)
    assert res_runtime is not None
    assert res_runtime.is_deny
    assert "runtime_gate_write_forbidden" in str(res_runtime.reason)

    # 2. Immutable recorded artifact overwrite attempt
    recorded_file = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-085" / "qa-01.yaml"
    events_dir = tmp_path / "memory-bank" / "back" / "events" / "T-HUB-085"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "events.jsonl").write_text(
        json.dumps({"artifact": "memory-bank/back/qa/T-HUB-085/qa-01.yaml", "kind": "qa_pass"}) + "\n",
        encoding="utf-8",
    )

    ctx_immutable = EventContext(
        event_name=PreToolUse,
        tool_name="Edit",
        tool_input={
            "file_path": str(recorded_file),
            "contents": "new content",
        },
        cwd=tmp_path,
        raw_payload={
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(recorded_file),
                "contents": "new content",
            },
            "cwd": str(tmp_path),
        },
    )
    res_immutable = adapter.evaluate(ctx_immutable)
    assert res_immutable is not None
    assert res_immutable.is_deny
    assert "recorded_artifact_immutable" in str(res_immutable.reason)


# ============================================================================
# CP3 / TDD: Boundary & Precedence
# ============================================================================

def test_pretool_finish_boundary_precedence(tmp_path: Path) -> None:
    """Parity test: Finish boundary runs first and denies any tool after successful mb-finish."""
    old_loop = os.environ.get("EPIC_LOOP")
    old_proj = os.environ.get("PROJECT_ROOT")
    old_dev_hub = os.environ.get("DEV_HUB")
    old_hub_root = os.environ.get("HUB_ROOT")

    os.environ["EPIC_LOOP"] = "1"
    os.environ["PROJECT_ROOT"] = str(tmp_path)
    os.environ.pop("DEV_HUB", None)
    os.environ.pop("HUB_ROOT", None)

    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase_run_id": "phase-run-123",
            "last_finish_tool": {
                "name": "mb-finish implement",
                "phase_run_id": "phase-run-123",
            },
        }
    )
    save_epic_state(tmp_path, state)

    try:
        # All tool types (Read, Write, Bash, Agent, Glob) must be denied by finish boundary
        for tname in ["Read", "Write", "Bash", "Agent", "Glob"]:
            payload = {
                "event_name": "PreToolUse",
                "tool_name": tname,
                "tool_input": {"command": "ls", "file_path": str(tmp_path / "foo.py")},
                "cwd": str(tmp_path),
            }
            res = dispatch_pretool_event(payload)
            assert res.is_deny
            assert res.diagnostic_code == DiagnosticCode.FINISH_BOUNDARY_DENY
            assert "finish_boundary" in str(res.reason)
    finally:
        if old_loop is not None:
            os.environ["EPIC_LOOP"] = old_loop
        else:
            os.environ.pop("EPIC_LOOP", None)
        if old_proj is not None:
            os.environ["PROJECT_ROOT"] = old_proj
        else:
            os.environ.pop("PROJECT_ROOT", None)
        if old_dev_hub is not None:
            os.environ["DEV_HUB"] = old_dev_hub
        if old_hub_root is not None:
            os.environ["HUB_ROOT"] = old_hub_root


def test_project_boundary_denies_outside_access(tmp_path: Path) -> None:
    """Project boundary denies filesystem and bash access outside project root."""
    adapter = ProjectBoundaryAdapter()

    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Read",
        tool_input={"file_path": "/etc/passwd"},
        cwd=tmp_path,
    )
    res = adapter.evaluate(ctx)
    assert res is not None
    assert res.is_deny
    assert res.diagnostic_code == DiagnosticCode.PROJECT_BOUNDARY_DENY


# ============================================================================
# CP4 / Functional: CLI Dispatcher End-to-End Execution
# ============================================================================

def test_cli_pretool_dispatch_allow_with_updated_input(tmp_path: Path) -> None:
    """CLI dispatcher outputs valid hook envelope with updatedInput."""
    from _lib import save_state
    save_state("cli-sess", str(ROOT), {"active": True, "mode": "IMPLEMENT", "workflow_active": True})

    valid_prompt = (
        "agent_type: worker\n"
        "GATE_IDENTITY session_id=cli-sess epic_id=T-HUB-085 step_id=s03\n"
        "Run tasks."
    )
    payload = {
        "event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"agent_type": "worker", "prompt": valid_prompt},
        "cwd": str(ROOT),
        "session_id": "cli-sess",
    }
    res = _run_cli(payload)
    out = res.get("hookSpecificOutput", {})
    assert out.get("hookEventName") == "PreToolUse"
    assert out.get("permissionDecision") == "allow"
    assert out.get("updatedInput", {}).get("subagent_type") == "worker"


def test_cli_pretool_dispatch_deny_on_boundary(tmp_path: Path) -> None:
    """CLI dispatcher denies project boundary violation."""
    payload = {
        "event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "/root/.ssh/id_rsa"},
        "cwd": str(tmp_path),
    }
    res = _run_cli(payload)
    out = res.get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"
    assert "project_boundary" in out.get("permissionDecisionReason", "") or "outside_project" in out.get("permissionDecisionReason", "")
