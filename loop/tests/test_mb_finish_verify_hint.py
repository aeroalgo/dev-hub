"""Tests for verify agent → mb-finish hint mapping."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))


def test_mb_finish_hint_implement_uses_armed_step(tmp_path: Path) -> None:
    from loop.mb_finish.verify_hint import mb_finish_cli, mb_finish_hint_after_verdict

    hooks = ROOT / "harness" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
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


def test_verify_qa_blocked_maps_to_bugfix_finish() -> None:
    from loop.mb_finish.verify_hint import mb_finish_cli

    cli = mb_finish_cli("verify-qa", "BLOCKED", "/tmp")
    assert cli is not None
    assert "mb-finish bugfix" in cli
