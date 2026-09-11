"""Parity and functional test suite for canonical PostToolUse dispatcher and policies.

Covers:
- CP1: Agent/Task posttool verdict persistence, gate identity sync, and in_flight release.
- CP2: Bash posttool output capping, signal extraction, and full dump retention.
- CP3: Repeated PostToolUse event delivery idempotency and single evidence recording.
- CP4: End-to-end CLI execution, exception safety, and disjoint branch isolation.
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

from hook_dispatch import (
    DecisionEnvelope,
    DiagnosticCode,
    DispatchBranch,
    EventContext,
    PostToolUse,
    dispatch_posttool,
)
from posttool_policy import (
    AgentPostToolAdapter,
    BashOutputCapAdapter,
    WritePostToolAdapter,
    create_posttool_branches,
    dispatch_posttool_event,
)
from _lib import (
    clear_in_flight,
    current_gate_identity,
    load_state,
    mark_in_flight,
    save_state,
)


def _run_cli(payload: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    cmd = [sys.executable, str(HOOKS / "posttool-dispatch.py")]
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        env=run_env,
    )
    assert proc.returncode == 0, f"Dispatcher failed with stderr: {proc.stderr}"
    if not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout)


# ============================================================================
# CP1: Agent posttool handler, verdict recording, in_flight clearing
# ============================================================================

def test_posttool_agent_evidence_recording(tmp_path: Path) -> None:
    """AgentPostToolAdapter parses verdict, records evidence, and syncs gate identity."""
    session_id = "test-agent-sess-01"
    save_state(session_id, str(tmp_path), {"active": True, "mode": "IMPLEMENT"})

    adapter = AgentPostToolAdapter()
    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Agent",
        tool_input={"subagent_type": "verify-implement"},
        tool_output="Checklist completed.\nVERDICT: PASS",
        cwd=tmp_path,
        session_id=session_id,
        raw_payload={
            "agent_type": "verify-implement",
            "tool_use_id": "call-001",
            "tool_response": "Checklist completed.\nVERDICT: PASS",
            "cwd": str(tmp_path),
            "session_id": session_id,
        },
    )

    env = adapter.evaluate(ctx)
    assert env is not None
    assert env.diagnostic_code == DiagnosticCode.RECORDED
    assert "PASS" in (env.reason or "")

    st = load_state(session_id, str(tmp_path))
    assert st.get("verify_verdict") == "PASS" or st.get("verify-implement_verdict") == "PASS"


def test_posttool_agent_clears_in_flight_marker(tmp_path: Path) -> None:
    """AgentPostToolAdapter releases in_flight state when agent finishes."""
    session_id = "test-in-flight-sess"
    st = {"in_flight": []}
    mark_in_flight(st, agent="verify-implement", model="gpt-5.6-luna", managed=True, cwd=str(tmp_path), session_id=session_id)
    save_state(session_id, str(tmp_path), st)

    # Verify marked in-flight
    assert any(e.get("agent") == "verify-implement" for e in st.get("in_flight", []))

    adapter = AgentPostToolAdapter()
    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Agent",
        tool_input={"subagent_type": "verify-implement"},
        tool_output="VERDICT: PASS",
        cwd=tmp_path,
        session_id=session_id,
        raw_payload={"agent_type": "verify-implement", "cwd": str(tmp_path), "session_id": session_id},
    )

    adapter.evaluate(ctx)

    st_after = load_state(session_id, str(tmp_path))
    assert not any(e.get("agent") == "verify-implement" for e in st_after.get("in_flight", []))


def test_posttool_agent_handles_repair_in_flight(tmp_path: Path) -> None:
    """When repair_in_flight is active, agent posttool clears it and requires verify retry."""
    session_id = "test-repair-sess"
    save_state(session_id, str(tmp_path), {"repair_in_flight": True})

    adapter = AgentPostToolAdapter()
    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Agent",
        tool_input={"subagent_type": "gate-repair"},
        tool_output="Repair completed.\nVERDICT: PASS",
        cwd=tmp_path,
        session_id=session_id,
        raw_payload={"agent_type": "gate-repair", "cwd": str(tmp_path), "session_id": session_id},
    )

    env = adapter.evaluate(ctx)
    assert env is not None

    st_after = load_state(session_id, str(tmp_path))
    assert st_after.get("repair_in_flight") is False
    assert st_after.get("gate_diagnostic") == "repair_complete_verify_required"


# ============================================================================
# CP2: Bash posttool handler, output capping, full dump retention
# ============================================================================

def test_posttool_bash_output_shaping_and_dump(tmp_path: Path) -> None:
    """BashOutputCapAdapter caps output exceeding threshold and writes full dump."""
    session_id = "test-bash-sess"
    adapter = BashOutputCapAdapter()

    large_output = "line of pytest output\n" * 1000 + "FAILED tests/test_foo.py::test_bar - AssertionError\n"
    assert len(large_output) > 12000

    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Bash",
        tool_input={"command": "pytest"},
        tool_output={"stdout": large_output, "stderr": ""},
        cwd=tmp_path,
        session_id=session_id,
        raw_payload={
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": {"stdout": large_output, "stderr": ""},
            "cwd": str(tmp_path),
            "session_id": session_id,
        },
    )

    env = adapter.evaluate(ctx)
    assert env is not None
    assert env.diagnostic_code == DiagnosticCode.OUTPUT_CAPPED
    assert env.updated_input is not None
    assert len(env.updated_input["stdout"]) < len(large_output)

    # Check dump file was created
    dumps_dir = tmp_path / ".claude" / "runtime" / "bash-dumps"
    assert dumps_dir.is_dir()
    dump_files = list(dumps_dir.glob("*.log"))
    assert len(dump_files) == 1
    dump_content = dump_files[0].read_text(encoding="utf-8")
    assert "AssertionError" in dump_content
    assert f"chars: {len(large_output)}" in dump_content


def test_posttool_bash_retains_small_output_uncapped(tmp_path: Path) -> None:
    """Small output within threshold is left untouched without dump."""
    adapter = BashOutputCapAdapter()
    small_output = "All tests passed!\n"

    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Bash",
        tool_input={"command": "echo hello"},
        tool_output={"stdout": small_output, "stderr": ""},
        cwd=tmp_path,
        session_id="test-small-sess",
    )

    env = adapter.evaluate(ctx)
    assert env is not None
    assert env.is_allow
    assert env.reason == "output_within_limit"
    assert env.updated_input is None


def test_posttool_exception_safety_retains_dump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If signal extraction or structured view fails, head-tail fallback still retains dump."""
    adapter = BashOutputCapAdapter()
    large_output = "some log data\n" * 1500

    def bad_build_view(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("Simulated build_view failure")

    monkeypatch.setattr("posttool_policy.build_view", bad_build_view)

    ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Bash",
        tool_input={"command": "run_job"},
        tool_output={"stdout": large_output, "stderr": ""},
        cwd=tmp_path,
        session_id="test-safe-sess",
        raw_payload={
            "tool_name": "Bash",
            "tool_input": {"command": "run_job"},
            "tool_response": {"stdout": large_output, "stderr": ""},
            "cwd": str(tmp_path),
            "session_id": "test-safe-sess",
        },
    )

    env = adapter.evaluate(ctx)
    assert env is not None
    assert env.diagnostic_code == DiagnosticCode.OUTPUT_CAPPED
    # Dump exists despite build_view error
    dumps = list((tmp_path / ".claude" / "runtime" / "bash-dumps").glob("*.log"))
    assert len(dumps) == 1


# ============================================================================
# CP3: Idempotency of repeated PostToolUse event delivery
# ============================================================================

def test_posttool_repeated_event_idempotent(tmp_path: Path) -> None:
    """Delivering the exact same PostToolUse payload multiple times does not duplicate state records."""
    session_id = "test-idempotent-sess"
    save_state(session_id, str(tmp_path), {"active": True})

    payload = {
        "event_name": "PostToolUse",
        "tool_name": "Agent",
        "agent_type": "verify-implement",
        "tool_use_id": "call-idem-1",
        "tool_response": "VERDICT: PASS\nAll checks green.",
        "cwd": str(tmp_path),
        "session_id": session_id,
    }

    # First delivery
    ctx1 = EventContext.from_payload(payload)
    env1 = dispatch_posttool_event(ctx1)
    assert env1.diagnostic_code == DiagnosticCode.RECORDED

    st1 = load_state(session_id, str(tmp_path))
    verdict_keys1 = list(st1.get("recorded_verdict_keys", []))

    # Second delivery with identical event
    ctx2 = EventContext.from_payload(payload)
    env2 = dispatch_posttool_event(ctx2)
    assert env2.diagnostic_code == DiagnosticCode.RECORDED

    st2 = load_state(session_id, str(tmp_path))
    verdict_keys2 = list(st2.get("recorded_verdict_keys", []))

    assert len(verdict_keys1) == len(verdict_keys2)
    assert st1.get("gates") == st2.get("gates")


# ============================================================================
# CP4: Disjoint branch isolation and CLI End-to-End
# ============================================================================

def test_posttool_agent_and_bash_disjoint_routing(tmp_path: Path) -> None:
    """Agent adapter ignores Bash tool; Bash adapter ignores Agent tool."""
    agent_adapter = AgentPostToolAdapter()
    bash_adapter = BashOutputCapAdapter()

    bash_ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Bash",
        tool_input={"command": "echo 1"},
        tool_output="1",
        cwd=tmp_path,
    )
    agent_ctx = EventContext(
        event_name=PostToolUse,
        tool_name="Agent",
        tool_input={"subagent_type": "worker"},
        tool_output="Done",
        cwd=tmp_path,
    )

    assert agent_adapter.evaluate(bash_ctx) is None
    assert bash_adapter.evaluate(agent_ctx) is None


def test_posttool_cli_e2e_agent_verdict(tmp_path: Path) -> None:
    """CLI dispatcher processes Agent verdict successfully."""
    session_id = "cli-agent-sess"
    save_state(session_id, str(tmp_path), {"active": True, "mode": "IMPLEMENT"})

    payload = {
        "event_name": "PostToolUse",
        "tool_name": "Agent",
        "agent_type": "verify-implement",
        "tool_use_id": "call-cli-01",
        "tool_response": "VERDICT: PASS",
        "cwd": str(tmp_path),
        "session_id": session_id,
    }

    res = _run_cli(payload)
    out = res.get("hookSpecificOutput", {})
    assert out.get("hookEventName") == "PostToolUse"
    assert out.get("diagnosticCode") == "recorded"


def test_posttool_cli_e2e_bash_output_capping(tmp_path: Path) -> None:
    """CLI dispatcher caps large bash output and outputs hookSpecificOutput."""
    session_id = "cli-bash-sess"
    large_output = "stdout data\n" * 1200

    payload = {
        "event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": {"stdout": large_output, "stderr": ""},
        "cwd": str(tmp_path),
        "session_id": session_id,
    }

    res = _run_cli(payload)
    out = res.get("hookSpecificOutput", {})
    assert out.get("hookEventName") == "PostToolUse"
    assert "updatedToolOutput" in out
    assert len(out["updatedToolOutput"]["stdout"]) < len(large_output)
    assert "output-cap" in out.get("additionalContext", "")
