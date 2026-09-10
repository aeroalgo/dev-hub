from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness" / "hooks"))


def _run_stop(
    tmp_path: Path,
    *,
    fence: dict,
    agent_type: str,
    session_id: str,
    runtime_id: str,
    tool_use_id: str = "wait-1",
) -> subprocess.CompletedProcess[str]:
    stop = ROOT / "harness" / "hooks" / "subagent-stop.py"
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
    env["EPIC_RUNTIME"] = runtime_id
    env["EPIC_RUNTIME_RESOLVED"] = runtime_id
    return subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
        env=env,
    )


def test_codex_session_id_label_is_coerced(tmp_path: Path) -> None:
    from epic.core import default_state, save_epic_state

    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "armed_epic": "T-HUB-079-orchestrator-lifecycle-reliability",
            "armed_step": "s02",
            "session_id": "b667d6da-b99f-46c5-8af5-0e66e3c447fd",
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-implement",
        "verdict": "FAIL",
        "step_id": "s02",
        "epic_id": "T-HUB-079-orchestrator-lifecycle-reliability",
        "session_id": "verify-implement-s02",
        "recorded_at": "2026-09-09T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-implement",
        session_id="b667d6da-b99f-46c5-8af5-0e66e3c447fd",
        runtime_id="codex",
    )
    assert "semantic_ownership_mismatch" not in proc.stderr
    assert proc.returncode == 0


def test_codex_step_id_and_epic_id_are_coerced_from_transport(tmp_path: Path) -> None:
    """Codex has no pre-spawn SubagentStart; wrong LLM step/epic must bind to runner identity."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-080-workflow-capability-instruction-parity"
    session_id = "bugfix-20260910-codex-ownership-coerce"
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
        "step_id": "s05",
        "epic_id": "T-HUB-999-foreign-epic",
        "session_id": "verify-bugfix-label",
        "recorded_at": "2026-09-10T12:00:00Z",
    }
    proc = _run_stop(
        tmp_path,
        fence=fence,
        agent_type="verify-bugfix",
        session_id=session_id,
        runtime_id="codex",
    )
    assert "semantic_ownership_mismatch" not in proc.stderr, proc.stderr
    assert "step_id mismatch" not in proc.stderr
    assert proc.returncode == 0


def test_claude_keeps_strict_step_id_ownership(tmp_path: Path) -> None:
    """Claude SubagentStart injects GATE_IDENTITY; stale step_id stays fail-closed."""
    from epic.core import default_state, save_epic_state

    epic = "T-HUB-080-workflow-capability-instruction-parity"
    session_id = "bugfix-20260910-claude-ownership-strict"
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
    assert "semantic_ownership_mismatch" in proc.stderr
    assert "step_id mismatch" in proc.stderr
