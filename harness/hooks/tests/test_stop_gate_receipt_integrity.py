"""Red tests for stop-gate handling of TaskStop, stale state, and absent receipts.

Covers:
- CP3: TaskStop / absent receipt produces infrastructure_failure, retains forensic state, no retry loop
- Stale verifier in-flight handling
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
STOP_GATE = ROOT / ".claude" / "hooks" / "stop-gate.py"
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from _lib import load_state, save_state


def _ensure_gate_agents(cwd: Path) -> None:
    agents = cwd / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    specs = (
        ("verify", "gate", "pass-fail", True),
        ("reviewer", "gate", "pass-blocked-fail", True),
    )
    for name, mode, verdict, requires_model in specs:
        path = agents / f"{name}.md"
        if not path.is_file():
            path.write_text(
                "---\n"
                f"name: {name}\n"
                "overlay:\n"
                "  managed: true\n"
                f"  mode: {mode}\n"
                f"  requires_model: {str(requires_model).lower()}\n"
                "  default_loop: true\n"
                "  default_chat: false\n"
                f"  verdict: {verdict}\n"
                "  allow_worktree: false\n"
                "---\nbody\n",
                encoding="utf-8",
            )
    env_path = cwd / ".claude" / "project.env"
    if not env_path.is_file():
        env_path.write_text(
            "PROJECT_WORKFLOW_HOOKS=loop\n"
            "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
            "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n",
            encoding="utf-8",
        )


def _run_stop_gate(cwd: Path, payload: dict) -> dict:
    _ensure_gate_agents(cwd)
    env = os.environ.copy()
    env["EPIC_LOOP"] = "1"
    proc = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def test_stop_gate_taskstop_or_stale_in_flight_retains_forensics_and_no_retry(tmp_path: Path):
    """FR-004, AC+4, TM-077-03: TaskStop/abrupt verifier termination records infrastructure failure without retry loop."""
    # Write initial handoff
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-077\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-T-HUB-077/s01.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Дальше:** @verify\n",
        encoding="utf-8",
    )

    # Set in_flight verify state as if TaskStop happened
    session_id = "test-taskstop-session"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s01",
        "in_flight": ["verify"],
        "in_flight_agents": {"verify": {"tool_use_id": "call_123", "started_at": "2026-09-07T10:00:00Z"}},
        "verify_done": False,
        "verify_verdict": None,
        "need_verify": True,
    }
    save_state(session_id, str(tmp_path), st)

    # Parent attempts to finish with in_flight verify / TaskStop
    res = _run_stop_gate(
        tmp_path,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH BACK IMPLEMENT — TaskStop on verify subagent.",
            "stop_hook_active": False,
        },
    )

    # In flight must not allow silent finish or infinite implicit retry
    assert res.get("decision") == "block"
    # State must retain forensic diagnostic
    st_after = load_state(session_id, str(tmp_path))
    assert st_after.get("in_flight") or st_after.get("gate_diagnostic") in (
        "agent_in_flight",
        "infrastructure_failure",
        "stale_verifier",
    )


def test_stop_gate_absent_receipt_with_finish_attempt_blocked(tmp_path: Path):
    """FR-004, AC+4: Absent receipt on finish attempt is blocked by stop gate."""
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-077\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-T-HUB-077/s01.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Дальше:** finalize\n",
        encoding="utf-8",
    )
    session_id = "test-absent-receipt"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s01",
        "verify_done": False,
        "verify_verdict": None,
    }
    save_state(session_id, str(tmp_path), st)

    res = _run_stop_gate(
        tmp_path,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH BACK IMPLEMENT — done.",
            "stop_hook_active": False,
        },
    )
    assert res.get("decision") == "block"
