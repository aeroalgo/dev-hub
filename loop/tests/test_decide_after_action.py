from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_halt_logic():
    path = ROOT / "loop" / "halt_logic.py"
    spec = importlib.util.spec_from_file_location("halt_logic", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def decide():
    return _load_halt_logic().decide_after_action


def test_halt_true_bool(decide) -> None:
    assert decide({"halt": True, "ok": False}) == "halt"


def test_halt_string_one(decide) -> None:
    assert decide({"halt": "1", "ok": False}) == "halt"


def test_halt_int_one(decide) -> None:
    assert decide({"halt": 1, "ok": False}) == "halt"


def test_need_human_verify_no_verdict(decide) -> None:
    assert (
        decide(
            {
                "ok": True,
                "complete": True,
                "stop": "NEED_HUMAN: verify_no_verdict",
            }
        )
        == "halt"
    )


def test_need_human_manual_review(decide) -> None:
    assert (
        decide(
            {
                "ok": True,
                "complete": True,
                "stop": "NEED_HUMAN: manual review",
            }
        )
        == "halt"
    )


def test_epic_done_complete(decide) -> None:
    assert decide({"ok": True, "complete": True, "stop": "EPIC_DONE"}) == "complete"


def test_ok_continue_fingerprint_stall_retry(decide) -> None:
    assert (
        decide(
            {
                "ok": True,
                "halt": False,
                "complete": False,
                "retry": True,
                "retry_fingerprint_stall": True,
                "reason": "outer retry 1/3",
            }
        )
        == "continue"
    )


def test_ok_continue_fingerprint(decide) -> None:
    assert (
        decide(
            {
                "ok": True,
                "complete": False,
                "fingerprint": "abc",
            }
        )
        == "continue"
    )


def test_ok_unchanged_normal_step(decide) -> None:
    assert decide({"ok": True, "complete": False}) == "continue"


def test_unknown_payload_fail_closed(decide) -> None:
    assert decide({"weird": True}) == "halt"


def test_repair_exhausted_integrity_halt(decide) -> None:
    assert (
        decide(
            {
                "ok": False,
                "halt": True,
                "repair_exhausted": True,
                "reason": "finish integrity failed",
            }
        )
        == "halt"
    )


def test_repair_exhausted_without_halt_flag(decide) -> None:
    assert (
        decide(
            {
                "ok": False,
                "repair_exhausted": True,
                "reason": "non-retryable integrity",
            }
        )
        == "halt"
    )


def test_halt_flag_beats_epic_done(decide) -> None:
    assert decide({"halt": True, "stop": "EPIC_DONE", "complete": True}) == "halt"


def test_need_human_beats_complete_flag(decide) -> None:
    assert (
        decide({"ok": True, "complete": True, "stop": "NEED_HUMAN: x"}) == "halt"
    )
