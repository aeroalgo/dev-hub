from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness" / "hooks"))


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

    stop = ROOT / "harness" / "hooks" / "subagent-stop.py"
    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-implement",
        "verdict": "FAIL",
        "step_id": "s02",
        "epic_id": "T-HUB-079-orchestrator-lifecycle-reliability",
        "session_id": "verify-implement-s02",
        "recorded_at": "2026-09-09T12:00:00Z",
    }
    payload = {
        "agent_type": "verify-implement",
        "session_id": "b667d6da-b99f-46c5-8af5-0e66e3c447fd",
        "runtime_id": "codex",
        "tool_use_id": "wait-1",
        "cwd": str(tmp_path),
        "last_assistant_message": "```json\n" + json.dumps(fence) + "\n```\n",
        "stop_hook_active": False,
    }
    env = os.environ.copy()
    env["EPIC_RUNTIME"] = "codex"
    proc = subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
        env=env,
    )
    assert "semantic_ownership_mismatch" not in proc.stderr
    assert proc.returncode == 0
