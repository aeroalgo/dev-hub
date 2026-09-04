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
    assert "- step: `s01`" in text
    assert "Silent chat (HARD)" in text
    assert "no thinking aloud" in text
    assert "mb-finish implement" in text
    assert "## IMPLEMENT FINISH" not in text
    assert "seed-implement" not in text


def test_build_prompt_qa_phase_omits_implement_finish():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK QA", "epic": "T-test", "next_step": "QA"},
    )
    assert "## IMPLEMENT FINISH" not in text
    assert "## QA FINISH" not in text
    assert "mb-finish qa" in text
    assert "## QA canon (HARD)" in text
    assert "bin/pytest -q --tb=line" in text
    assert "suite_not_full" in text
    assert "BACK BUGFIX" in text
    assert "code_changed: no" in text
    assert "чинит в сессии" not in text
    assert "это чинится в сессии: FAIL → fix → re-verify" not in text
    assert "FIX INCOMPLETE" not in text
    assert "verify-qa до full suite" in text


def test_build_prompt_implement_keeps_session_fix():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK IMPLEMENT", "epic": "T-test", "next_step": "s01"},
    )
    assert "это чинится в сессии: FAIL → fix → re-verify" in text
    assert "## QA canon (HARD)" not in text


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


def test_build_prompt_audit_phase_uses_mb_finish():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK AUDIT", "epic": "T-test", "next_step": "AUDIT", "role": "back"},
    )
    assert "mb-finish audit" in text
    assert "FORBIDDEN: ручной Write activeContext" in text
    assert "## AUDIT FINISH" not in text
    assert "AUDIT canon" in text
    assert "plan_vs_runtime" in text or "PLAN↔runtime" in text
    assert "FORBIDDEN: pytest" in text
    assert "это чинится в сессии: FAIL → fix → re-verify" not in text


def test_build_prompt_decompose_phase_uses_mb_finish():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK DECOMPOSE", "epic": "T-test", "next_step": "DECOMPOSE"},
    )
    assert "mb-finish decompose" in text
    assert "## DECOMPOSE FINISH" not in text


def test_build_prompt_analyze_phase_uses_mb_finish():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK ANALYZE", "epic": "T-test", "next_step": "ANALYZE"},
    )
    assert "mb-finish analyze" in text
    assert "## ANALYZE FINISH" not in text
