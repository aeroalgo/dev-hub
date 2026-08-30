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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_epic() -> object:
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    import epic

    return epic


def _prepare_epic(tmp_path: Path) -> None:
    _write(
        tmp_path / "memory-bank" / "activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-s05/index.md`\n\n"
        "## Handoff BACK IMPLEMENT — in progress\n- next\n",
    )
    _write(
        tmp_path / "memory-bank" / "back" / "plan" / "decompose-s05" / "index.md",
        "| Step | Status |\n| --- | --- |\n| **s05** | pending |\n",
    )
    epic = _load_epic()
    state = epic.default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "phase": "IMPLEMENT",
            "pending_fingerprint_before": epic.fingerprint_context(
                (tmp_path / "memory-bank" / "activeContext.md").read_text()
            ),
            "armed_step": "s05",
            "armed_decompose": "memory-bank/back/plan/decompose-s05/s05.yaml",
        }
    )
    epic.save_epic_state(tmp_path, state)


def _run(
    tmp_path: Path,
    session_id: str = "dsh-self-limit",
    self_limit: str | None = None,
) -> dict:
    env = os.environ.copy()
    env.update({"EPIC_LOOP": "1", "DSH_HOOKS_BRIDGE": "1"})
    env.pop("DSH_SELF_LIMIT_MAX", None)
    if self_limit is not None:
        env["DSH_SELF_LIMIT_MAX"] = self_limit
    env.pop("PROJECT_ROOT", None)
    env.pop("DEV_HUB", None)
    env.pop("HUB_ROOT", None)
    env["PROJECT_WORKFLOW_HOOKS"] = "loop"
    env["PROJECT_AGENT_VERIFY_MODEL"] = "sonnet"
    env["PROJECT_AGENT_REVIEWER_MODEL"] = "sonnet"
    env["PROJECT_AGENT_EXPLORER_MODEL"] = "fable"
    _write(
        tmp_path / ".claude" / "agents" / "verify.md",
        "---\nname: verify\noverlay:\n  managed: true\n  mode: gate\n  requires_model: true\n  default_loop: true\n  default_chat: false\n  verdict: pass-fail\n---\n",
    )
    _write(
        tmp_path / ".claude" / "agents" / "reviewer.md",
        "---\nname: reviewer\noverlay:\n  managed: true\n  mode: gate\n  requires_model: true\n  default_loop: true\n  default_chat: false\n  verdict: pass-blocked-fail\n---\n",
    )
    _write(
        tmp_path / ".claude" / "agents" / "explorer.md",
        "---\nname: explorer\noverlay:\n  managed: true\n  mode: search\n  requires_model: false\n  default_loop: true\n  default_chat: false\n  verdict: none\n---\n",
    )
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    env["PROJECT_ROOT"] = str(tmp_path)
    env["PYTHONPATH"] = str(HOOKS)
    proc = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        cwd=tmp_path,
        env=env,
        input=json.dumps(
            {
                "session_id": session_id,
                "cwd": str(tmp_path),
                "last_assistant_message": "FINISH: stop",
                "stop_hook_active": False,
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _load_spawn_state(tmp_path: Path, session_id: str = "dsh-self-limit") -> dict:
    path = tmp_path / ".claude" / "runtime" / "spawn-gate" / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_dsh_default_limit_is_eight(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)

    for _ in range(7):
        assert _run(tmp_path)["decision"] == "block"
    assert _load_spawn_state(tmp_path)["dsh_consecutive_blocks"] == 7

    result = _run(tmp_path)

    assert result["decision"] == "allow"
    assert "DSH self-limit" in result["reason"]


def test_dsh_block_under_limit(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)

    result = _run(tmp_path)

    assert result["decision"] == "block"
    assert _load_spawn_state(tmp_path)["dsh_consecutive_blocks"] == 1


def test_dsh_valid_configured_limit_is_honored(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)

    assert _run(tmp_path, self_limit="2")["decision"] == "block"
    result = _run(tmp_path, self_limit="2")

    assert result["decision"] == "allow"
    assert "DSH self-limit" in result["reason"]


def test_dsh_block_counter_increments(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)

    assert _run(tmp_path)["decision"] == "block"
    assert _run(tmp_path)["decision"] == "block"

    assert _load_spawn_state(tmp_path)["dsh_consecutive_blocks"] == 2


def test_dsh_allow_at_limit(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)
    state_path = tmp_path / ".claude" / "runtime" / "spawn-gate" / "dsh-self-limit.json"
    state = {"dsh_consecutive_blocks": 8}
    _write(state_path, json.dumps(state))

    result = _run(tmp_path)

    assert result["decision"] == "allow"
    assert "DSH self-limit" in result["reason"]


def test_dsh_invalid_configured_limit_fails_closed(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)

    result = _run(tmp_path, self_limit="0")

    assert result["decision"] == "block"
    assert "invalid DSH self-limit" in result["reason"]
    assert _load_spawn_state(tmp_path)["dsh_consecutive_blocks"] == 0


def test_dsh_counter_resets_on_fingerprint_progress(tmp_path: Path) -> None:
    _prepare_epic(tmp_path)
    assert _run(tmp_path)["decision"] == "block"

    _write(
        tmp_path / "memory-bank" / "activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-s05/s05.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — progressed\n- next s06\n",
    )
    result = _run(tmp_path)

    assert result == {}
    assert _load_spawn_state(tmp_path)["dsh_consecutive_blocks"] == 0
    assert _load_spawn_state(tmp_path).get("epic_stop_blocks") == 0
