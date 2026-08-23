from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))


def test_build_prompt_implement_finish_order_and_handoff():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK IMPLEMENT", "epic": "T-test", "next_step": "s01"},
    )
    assert "Silent chat (HARD)" in text
    assert "no thinking aloud" in text
    finish_section = text.split("## IMPLEMENT FINISH", 1)[1]

    assert "seed-implement" in finish_section
    assert "flush-checkpoint" in finish_section
    assert "Перепиши" in finish_section
    assert "memory-bank/activeContext.md" in finish_section
    assert "## Handoff" in finish_section
    assert "NEED_HUMAN: verify_no_verdict" in finish_section
    assert "BLOCKED: verify_no_verdict" not in finish_section


def test_build_prompt_qa_phase_omits_implement_finish():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK QA", "epic": "T-test", "next_step": "QA"},
    )
    assert "## IMPLEMENT FINISH" not in text
    assert "## QA FINISH" in text
    assert "@reviewer" in text
    assert "qa-YYYYMMDD-<slug>.yaml" in text
    assert "verdict: pass|fail|blocked" in text


def test_build_prompt_creative_omits_verify():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK CREATIVE", "epic": "T-test", "next_step": "s15"},
    )

    assert "## CREATIVE FINISH" in text
    assert "FORBIDDEN: `@verify` для CREATIVE." in text
    assert "FORBIDDEN: `mark-index-status --status completed` на CREATIVE" in text
    assert "## IMPLEMENT FINISH" not in text
