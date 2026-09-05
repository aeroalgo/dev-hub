"""Tests for external_gates integration in stop-gate."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STOP_GATE = ROOT / "harness" / "hooks" / "stop-gate.py"


def _run_stop_gate(cwd: Path, payload: dict, env_overrides: dict | None = None) -> dict:
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_") or key in (
            "DEV_HUB",
            "HUB_ROOT",
            "PROJECT_ROOT",
            "CLAUDE_PROJECT_DIR",
        ):
            env.pop(key)
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
    )
    assert proc.returncode == 0, f"stop-gate crashed: {proc.stderr}"
    if proc.stdout.strip():
        return json.loads(proc.stdout)
    return {}


def test_block_finish_on_gate_fail(tmp_path: Path) -> None:
    """stop-gate blocks FINISH for EDIT phase when render external gate fails (missing outputs/final.mp4)."""
    # 1. Setup video pack in project.yaml
    (tmp_path / "project.yaml").write_text("workflow_pack: video-production\n", encoding="utf-8")

    # 2. Setup state
    runtime_dir = tmp_path / ".claude" / "runtime"
    (runtime_dir / "epic").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "spawn-gate").mkdir(parents=True, exist_ok=True)

    epic_state = {
        "active": True,
        "status": "running",
        "phase": "EDIT",
        "armed_step": "s01",
    }
    (runtime_dir / "epic" / "state.json").write_text(json.dumps(epic_state), encoding="utf-8")

    spawn_state = {
        "mode": "implement",
        "workflow_source": "loop",
        "need_verify": False,
    }
    (runtime_dir / "spawn-gate" / "sess-1.json").write_text(json.dumps(spawn_state), encoding="utf-8")

    payload = {
        "session_id": "sess-1",
        "cwd": str(tmp_path),
        "last_assistant_message": "FINISH: completed EDIT step",
        "stop_hook_active": False,
    }

    res = _run_stop_gate(tmp_path, payload)
    assert res.get("decision") == "block"
    assert "external gate 'render' check failed" in res.get("reason", "")
    assert "render_output_missing" in res.get("reason", "")


def test_pass_finish_on_gate_pass(tmp_path: Path) -> None:
    """stop-gate allows (does not block on external gate) when render external gate passes."""
    (tmp_path / "project.yaml").write_text("workflow_pack: video-production\n", encoding="utf-8")

    # Fixture mp4
    out_file = tmp_path / "outputs" / "final.mp4"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(b"dummy mp4 fixture payload")

    runtime_dir = tmp_path / ".claude" / "runtime"
    (runtime_dir / "epic").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "spawn-gate").mkdir(parents=True, exist_ok=True)

    epic_state = {
        "active": True,
        "status": "running",
        "phase": "EDIT",
        "armed_step": "s01",
    }
    (runtime_dir / "epic" / "state.json").write_text(json.dumps(epic_state), encoding="utf-8")

    spawn_state = {
        "mode": "implement",
        "workflow_source": "chat",
        "need_verify": False,
    }
    (runtime_dir / "spawn-gate" / "sess-2.json").write_text(json.dumps(spawn_state), encoding="utf-8")

    payload = {
        "session_id": "sess-2",
        "cwd": str(tmp_path),
        "last_assistant_message": "FINISH: completed EDIT step",
        "stop_hook_active": False,
    }

    res = _run_stop_gate(tmp_path, payload)
    # Shouldn't be blocked by external gate
    if res.get("decision") == "block":
        assert "external gate" not in res.get("reason", "")
