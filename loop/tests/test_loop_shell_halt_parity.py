"""Static shell wiring: check-after → decide_after_action halt-parity (s02)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP_SH = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")


def _check_after_block() -> str:
    """Slice from check-after invoke to end of outer while."""
    marker = 'check-after --fingerprint-before'
    assert marker in LOOP_SH
    start = LOOP_SH.index(marker)
    end = LOOP_SH.rindex("\ndone\n") + len("\ndone\n")
    return LOOP_SH[start:end]


def test_loop_sh_wires_decide_after_action() -> None:
    assert "from halt_logic import decide_after_action" in LOOP_SH
    assert "decide_after_action(" in LOOP_SH


def test_need_human_path_exits_not_retry() -> None:
    block = _check_after_block()
    assert "NEED_HUMAN" in block
    assert 'after_stop" == NEED_HUMAN*' in block or "NEED_HUMAN —" in block
    assert "exit 1" in block
    assert "not EPIC_DONE) — retrying outer loop" not in block
    assert 'stop=$after_stop (not EPIC_DONE)' not in block


def test_check_after_nonzero_not_unconditional_outer_retry() -> None:
    block = _check_after_block()
    assert "check-after failed (rc=$after_rc) — retrying outer loop" not in block
    # halt-parity uses decide_after_action, not raw after_rc retry
    assert 'after_action' in block
    assert '== "halt"' in block or "== 'halt'" in block or '== "halt"' in block


def test_prepare_fail_closed_still_halts() -> None:
    assert "HALT: prepare fail-closed" in LOOP_SH
    assert 'prep_halt" == "1"' in LOOP_SH or "prep_halt\" == \"1\"" in LOOP_SH
    # prepare block still exits on halt
    prep_idx = LOOP_SH.index("HALT: prepare fail-closed")
    window = LOOP_SH[prep_idx : prep_idx + 200]
    assert "exit" in window


def test_epic_done_complete_path_retained() -> None:
    block = _check_after_block()
    assert "roadmap-advance" in block
    assert "dag-fanout" in block
    assert "LOOP COMPLETE" in block


def test_loop_has_no_max_iterations_cap() -> None:
    assert "while true" in LOOP_SH
    assert "MAX_ITER" not in LOOP_SH
    assert "EPIC_MAX" not in LOOP_SH
    assert "LOOP HALTED: max iterations" not in LOOP_SH
    assert "POST_IMPLEMENT_RESERVE" not in LOOP_SH
