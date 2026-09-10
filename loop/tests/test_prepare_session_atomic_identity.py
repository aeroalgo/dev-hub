from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from epic.core import load_epic_state, save_epic_state
from harness.hooks._lib import load_state, mark_in_flight, save_state
from loop.gate_identity import GateIdentity
from loop.session_finalize import freeze_session_start_identity


def _load_context_loop(name: str):
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    path = root / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    ctx = importlib.util.module_from_spec(spec)
    hooks = str(root / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(ctx)
    return ctx


def test_prepare_mirrors_spawn_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Unit: freeze_session_start_identity mirrors gate_identity directly
    state: dict[str, Any] = {
        "armed_epic": "T-HUB-091-gate-identity-sot-consolidation",
        "armed_step": "s02",
        "role": "BACK",
        "session_id": "sess-atomic-prepare",
        "phase_run_id": "run-001",
    }
    frozen = freeze_session_start_identity(
        state,
        phase="BACK IMPLEMENT",
        step_id="s02",
        session_id="sess-atomic-prepare",
        phase_run_id="run-001",
    )
    assert state.get("session_start_identity") is not None
    assert state.get("gate_identity") is not None
    assert state["session_start_identity"]["step_id"] == "s02"
    assert state["gate_identity"]["step"] == "s02"
    assert state["gate_identity"]["step_id"] == "s02"
    assert state["gate_identity"]["epic_id"] == "T-HUB-091-gate-identity-sot-consolidation"
    assert state["gate_identity"]["session_id"] == "sess-atomic-prepare"
    assert state["gate_identity"]["role"] == "BACK"

    # Mid-session drift: armed_step / projection advances
    state["armed_step"] = "QA"
    state["projection"] = {"step": "QA", "epic_id": "T-DRIFT"}
    sot = GateIdentity.expected(state)
    assert sot.step_id == "s02"
    assert sot.step == "s02"
    assert sot.epic_id == "T-HUB-091-gate-identity-sot-consolidation"

    mirrored = GateIdentity.bind_spawn_gate(state)
    assert mirrored["step"] == "s02"
    assert state["gate_identity"]["step"] == "s02"

    # 2. Integration: prepare_session writes both session_start_identity and gate_identity
    ctx = _load_context_loop("context_loop_atomic_prepare")
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    epic = "T-HUB-091-test-atomic"
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic}\n"
        "step_id: s02\n"
        "---\n\n"
        "## load_now\n"
        "1. [memory-bank/activeContext.md](memory-bank/activeContext.md)\n",
        encoding="utf-8",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_step": "s02",
            "role": "BACK",
            "active": True,
            "status": "armed",
        },
    )

    res = ctx.prepare_session(tmp_path)
    assert res.get("ok") is True, res

    persisted = load_epic_state(tmp_path)
    assert persisted.get("session_start_identity") is not None
    assert persisted.get("gate_identity") is not None
    assert persisted["session_start_identity"]["step_id"] == "s02"
    assert persisted["gate_identity"]["step"] == "s02"
    assert persisted["gate_identity"]["epic_id"] == epic
    assert persisted["gate_identity"]["session_id"] == persisted["session_start_identity"]["session_id"]


def test_pretool_binds_spawn_gate_sot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Unit: mark_in_flight binds spawn gate mirror from SoT
    state: dict[str, Any] = {
        "session_start_identity": {
            "step_id": "s02",
            "epic_id": "T-HUB-091-pretool",
            "session_id": "sess-pretool-1",
            "role": "BACK",
        }
    }
    mark_in_flight(
        state,
        agent="verify-implement",
        model="gpt-5.6-luna",
        managed=True,
        tool_use_id="call_abc123",
    )
    assert len(state["in_flight"]) == 1
    assert state["in_flight"][0]["agent"] == "verify-implement"
    assert state["in_flight"][0]["tool_use_id"] == "call_abc123"
    assert state.get("gate_identity") is not None
    assert state["gate_identity"]["step"] == "s02"
    assert state["gate_identity"]["epic_id"] == "T-HUB-091-pretool"
    assert state["gate_identity"]["session_id"] == "sess-pretool-1"

    # 2. Integration: agent-pretool.py CLI execution
    session_id = "sess-pretool-cli"
    epic = "T-HUB-091-pretool-cli"

    # Setup agent metadata and project.env in isolated tmp_path
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "verify-implement.md").write_text(
        "---\nname: verify-implement\noverlay:\n  managed: true\n  requires_model: true\n  default_loop: true\n---\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_IMPLEMENT_MODEL=gpt-5.6-luna\n",
        encoding="utf-8",
    )

    # Setup activeContext.md for epic environment validation
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic}\n"
        "step_id: s02\n"
        "---\n\n"
        "## load_now\n"
        "1. [memory-bank/activeContext.md](memory-bank/activeContext.md)\n",
        encoding="utf-8",
    )

    # Setup implement shard
    impl_shard = tmp_path / "memory-bank" / "back" / "implement" / epic / "s02-atomic.yaml"
    impl_shard.parent.mkdir(parents=True, exist_ok=True)
    impl_shard.write_text("schema: epic-implement/v1\nstep_id: s02\n", encoding="utf-8")
    dec_shard = tmp_path / "memory-bank" / "back" / "plan" / epic / "yaml" / "steps" / "s02-atomic.yaml"
    dec_shard.parent.mkdir(parents=True, exist_ok=True)
    dec_shard.write_text("schema: epic-decompose/v1\nstep_id: s02\n", encoding="utf-8")

    # Setup epic state with frozen session_start_identity
    save_epic_state(
        tmp_path,
        {
            "session_id": session_id,
            "session_start_identity": {
                "step_id": "s02",
                "epic_id": epic,
                "session_id": session_id,
                "role": "BACK",
                "phase": "BACK IMPLEMENT",
            },
            "armed_epic": epic,
            "armed_step": "s02",
            "role": "BACK",
            "active": True,
            "status": "running",
        },
    )

    # Setup gate state
    st = load_state(session_id, str(tmp_path))
    st["mode"] = "IMPLEMENT"
    save_state(session_id, str(tmp_path), st)

    # Prepare input for agent-pretool.py
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "verify-implement",
            "prompt": f"agent_type: verify-implement\nALLOW READ memory-bank/back/implement/{epic}/s02-atomic.yaml\nALLOW READ memory-bank/back/plan/{epic}/yaml/steps/s02-atomic.yaml\nVERIFY s02",
        },
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_use_id": "call_pretool_integration",
    }

    hook_script = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "agent-pretool.py"
    hooks_dir = Path(__file__).resolve().parents[2] / "harness" / "hooks"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(hooks_dir)
    env["EPIC_LOOP"] = "1"
    env.pop("PROJECT_ROOT", None)
    env.pop("DEV_HUB", None)
    env.pop("HUB_ROOT", None)

    proc = subprocess.run(
        [sys.executable, str(hook_script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"stdout: {proc.stdout}, stderr: {proc.stderr}"
    resp = json.loads(proc.stdout) if proc.stdout.strip() else {}
    decision = resp.get("hookSpecificOutput", {}).get("permissionDecision")
    assert decision == "allow", resp

    # Check updated gate state
    updated_st = load_state(session_id, str(tmp_path))
    assert any(
        e.get("agent") == "verify-implement" and e.get("tool_use_id") == "call_pretool_integration"
        for e in updated_st.get("in_flight", [])
    )
    assert updated_st.get("gate_identity") is not None
    assert updated_st["gate_identity"]["step"] == "s02"
    assert updated_st["gate_identity"]["epic_id"] == epic
    assert updated_st["gate_identity"]["session_id"] == session_id
