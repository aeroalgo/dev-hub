"""Tests for verify agent → mb-finish hint mapping."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
HOOKS = ROOT / "harness" / "hooks"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))


def test_mb_finish_hint_implement_uses_armed_step(tmp_path: Path) -> None:
    from loop.mb_finish.verify_hint import mb_finish_cli, mb_finish_hint_after_verdict

    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    from epic import load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st["armed_step"] = "s07"
    save_epic_state(tmp_path, st)

    cli = mb_finish_cli("verify-implement", "PASS", tmp_path)
    assert cli is not None
    assert "mb-finish implement" in cli
    assert "--step s07" in cli

    hint = mb_finish_hint_after_verdict("verify-implement", "PASS", tmp_path)
    assert hint is not None
    assert "FORBIDDEN: ручной Write activeContext" in hint


def test_mb_finish_hint_maps_all_verify_agents() -> None:
    from loop.mb_finish.verify_hint import VERIFY_MB_FINISH_SUBCMD, mb_finish_cli

    cases = {
        "verify-bugfix": "bugfix",
        "verify-decompose": "decompose",
        "verify-qa": "qa",
        "analyze-verify": "analyze",
    }
    for agent, subcmd in cases.items():
        assert VERIFY_MB_FINISH_SUBCMD[agent] == subcmd
        cli = mb_finish_cli(agent, "PASS", "/tmp")
        assert cli is not None
        assert f"mb-finish {subcmd}" in cli


def test_verify_qa_blocked_routes_to_bugfix_finish() -> None:
    from loop.mb_finish.verify_hint import mb_finish_cli, mb_finish_hint_after_verdict

    cli = mb_finish_cli("verify-qa", "BLOCKED", ".")
    assert cli is None
    hint = mb_finish_hint_after_verdict("verify-qa", "BLOCKED", ".")
    assert hint is not None
    assert "BUGFIX" in hint
    assert "gate-repair" not in hint
    assert "mb-finish" in hint
    assert "retry @verify-qa" not in hint
    assert "verify retry" in hint
    assert "eligible" in hint


def test_verify_qa_fail_routes_to_bugfix_finish() -> None:
    from loop.mb_finish.verify_hint import mb_finish_hint_after_verdict

    hint = mb_finish_hint_after_verdict("verify-qa", "FAIL", ".")
    assert hint is not None
    assert "BUGFIX" in hint
    assert "gate-repair" not in hint
    assert "retry @verify-qa" not in hint
    assert "verify retry" in hint
    assert "eligible" in hint
    assert "style" in hint.lower()


def test_subagent_stop_verify_qa_fail_emits_bugfix_hint_not_retry(tmp_path: Path) -> None:
    """Hook stderr must route verify-qa FAIL → qa.yaml/BUGFIX, never retry @verify-qa."""
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    from epic.core import default_state, save_epic_state

    epic_id = "T-HUB-080-workflow-capability-instruction-parity"
    session_id = "sess-qa-fail-no-retry"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK QA",
            "mode": "qa",
            "armed_epic": epic_id,
            "armed_step": "qa",
            "session_id": session_id,
        }
    )
    save_epic_state(tmp_path, st)

    payload = {
        "agent_type": "verify-qa",
        "session_id": session_id,
        "tool_use_id": "tool-qa-fail-hint",
        "cwd": str(tmp_path),
        "last_assistant_message": (
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify-qa",'
            f'"verdict":"FAIL","step_id":"qa","epic_id":"{epic_id}",'
            f'"session_id":"{session_id}","recorded_at":"2026-09-10T15:00:00Z"}}\n```\n'
        ),
        "stop_hook_active": False,
    }
    stop = HOOKS / "subagent-stop.py"
    proc = subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "retry @verify-qa" not in proc.stderr
    assert "BUGFIX" in proc.stderr
    assert "mb-finish" in proc.stderr
    assert "verify retry" in proc.stderr

