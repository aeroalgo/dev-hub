from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "harness" / "hooks"


def _run_start(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    start_hook = HOOKS / "subagent-start.py"
    event = {"session_id": "test-sess", "cwd": str(tmp_path), **payload}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    return subprocess.run(
        [sys.executable, str(start_hook)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _run_stop(
    tmp_path: Path,
    *,
    fence: dict,
    agent_type: str,
    session_id: str,
    runtime_id: str = "claude",
    tool_use_id: str = "wait-1",
) -> subprocess.CompletedProcess[str]:
    stop_hook = HOOKS / "subagent-stop.py"
    payload = {
        "agent_type": agent_type,
        "session_id": session_id,
        "runtime_id": runtime_id,
        "tool_use_id": tool_use_id,
        "cwd": str(tmp_path),
        "last_assistant_message": "```json\n" + json.dumps(fence) + "\n```\n",
        "stop_hook_active": False,
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    env["EPIC_RUNTIME"] = runtime_id
    env["EPIC_RUNTIME_RESOLVED"] = runtime_id
    return subprocess.run(
        [sys.executable, str(stop_hook)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
        env=env,
    )


def test_subagent_start_injects_sot(tmp_path: Path, monkeypatch) -> None:
    """FR-004, US-002, TM-002: SubagentStart injects exact SoT fields into additionalContext."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-sot-inject-1"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": "T-HUB-DRIFT",  # drift should be ignored in favor of frozen SoT
            "armed_step": "s99",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-001",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    proc = _run_start(
        tmp_path,
        {
            "agent_type": "verify-bugfix",
            "session_id": session_id,
            "runtime_id": "claude",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout
    data = json.loads(proc.stdout)
    context = data["hookSpecificOutput"]["additionalContext"]

    expected_identity_line = f"GATE_IDENTITY session_id={session_id} epic_id={epic} step_id=BUGFIX"
    assert expected_identity_line in context
    assert "Fence MUST use these exact IDs for session_id, epic_id, and step_id." in context
    assert "CONTRACT verify-bugfix:" in context


def test_subagent_stop_claude_strict_mismatch(tmp_path: Path) -> None:
    """FR-008, US-003, SC-002, TM-005: SubagentStop with mismatched step_id produces semantic_ownership_mismatch (exit 2)."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-claude-strict-1"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": epic,
            "armed_step": "BUGFIX",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    # Fence with stale step_id s05 instead of BUGFIX
    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "FAIL",
        "step_id": "s05",
        "epic_id": epic,
        "session_id": session_id,
        "recorded_at": "2026-09-10T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-bugfix",
        session_id=session_id,
        runtime_id="claude",
    )
    assert proc.returncode == 2
    assert "NEED_HUMAN: semantic_ownership_mismatch" in proc.stderr
    assert "step_id mismatch" in proc.stderr


def test_subagent_stop_claude_strict_epic_mismatch(tmp_path: Path) -> None:
    """SubagentStop with mismatched epic_id produces semantic_ownership_mismatch (exit 2)."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-claude-strict-2"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": epic,
            "armed_step": "BUGFIX",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "FAIL",
        "step_id": "BUGFIX",
        "epic_id": "T-HUB-999-foreign-epic",
        "session_id": session_id,
        "recorded_at": "2026-09-10T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-bugfix",
        session_id=session_id,
        runtime_id="claude",
    )
    assert proc.returncode == 2
    assert "NEED_HUMAN: semantic_ownership_mismatch" in proc.stderr
    assert "epic_id mismatch" in proc.stderr


def test_subagent_stop_claude_strict_session_mismatch(tmp_path: Path) -> None:
    """SubagentStop with mismatched session_id produces semantic_ownership_mismatch (exit 2)."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-claude-strict-3"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": epic,
            "armed_step": "BUGFIX",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "FAIL",
        "step_id": "BUGFIX",
        "epic_id": epic,
        "session_id": "wrong-sess-id",
        "recorded_at": "2026-09-10T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-bugfix",
        session_id=session_id,
        runtime_id="claude",
    )
    assert proc.returncode == 2
    assert "NEED_HUMAN: semantic_ownership_mismatch" in proc.stderr
    assert "session_id mismatch" in proc.stderr


def test_subagent_stop_claude_strict_success(tmp_path: Path) -> None:
    """SubagentStop succeeds with code 0 when fence matches SoT under strict policy."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-claude-strict-4"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": epic,
            "armed_step": "BUGFIX",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "FAIL",
        "step_id": "BUGFIX",
        "epic_id": epic,
        "session_id": session_id,
        "recorded_at": "2026-09-10T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-bugfix",
        session_id=session_id,
        runtime_id="claude",
    )
    assert proc.returncode == 0, proc.stderr
    assert "semantic_ownership_mismatch" not in proc.stderr
