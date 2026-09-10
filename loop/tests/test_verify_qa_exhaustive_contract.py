from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def test_verify_qa_prompt_requires_exhaustive_pass_and_complete_blockers():
    text = (ROOT / "harness" / "agents" / "verify-qa.md").read_text(encoding="utf-8")
    assert "Exhaustive pass (HARD)" in text
    assert "остановиться на первом дефекте" in text
    assert "fail-fast" in text.lower() or "Fail-fast" in text or "no fail-fast" in text.lower()
    assert "## BLOCKERS (complete)" in text
    assert "maxTurns: 30" in text
    assert "≤40" in text


def test_verify_qa_anti_ratchet_blocker_eligibility():
    text = (ROOT / "harness" / "agents" / "verify-qa.md").read_text(encoding="utf-8")
    assert "Blocker eligibility / anti-ratchet (HARD)" in text
    assert "Frozen checklist (HARD)" in text
    assert "Ineligible (FORBIDDEN в `## BLOCKERS`" in text
    assert "Style / naming / one-letter locals" in text
    assert "Unrequested comments" in text
    assert "ok (ineligible:" in text
    assert "suite_red" in text
    assert "prior_only" in text
    assert "checklist_sha256" in text or "Frozen QA checklist" in text


def test_allow_read_max_elevated_for_verify_qa():
    import _lib as lib

    assert lib.allow_read_max_for("verify-qa") == 40
    assert lib.allow_read_max_for("reviewer") == 40
    assert lib.allow_read_max_for("verify-implement") == 10

    paths = "\n".join(f"- f{i}.py" for i in range(25))
    prompt = f"## Suite results\nok\n## AC+\nx\n## AC−\ny\n## §0.11\nz\n## ALLOW READ\n{paths}\n"
    assert lib.allow_read_violations(prompt, agent_type="verify-qa") == []
    assert any("25 файлов > 10" in v for v in lib.allow_read_violations(prompt, agent_type="verify-implement"))


def test_build_prompt_qa_requires_complete_blockers_report():
    LOOP = ROOT / "loop"
    if str(LOOP) not in sys.path:
        sys.path.insert(0, str(LOOP))
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={"phase": "BACK QA", "epic": "T-test", "next_step": "QA"},
    )
    assert "BLOCKERS (complete)" in text
    assert "fail-fast" in text
    assert "verify-qa до full suite" not in text
    assert "anti-ratchet" in text
    assert "eligible" in text
    assert "style" in text.lower()
    assert "Frozen QA checklist" in text


def test_qa_outcome_policy_includes_anti_ratchet():
    LOOP = ROOT / "loop"
    if str(LOOP) not in sys.path:
        sys.path.insert(0, str(LOOP))
    from qa_outcome import render_qa_outcome_policy
    from loop.schemas.qa_outcome import QaOutcome

    text = render_qa_outcome_policy(
        QaOutcome(
            schema="loop-qa-outcome/v1",
            kind="all_green",
            next_action="verify_qa",
            suite_scope="full",
            suite_command="bin/pytest -q --tb=line",
            reasons=["fresh_qa_full_suite"],
            epic_id="T-test",
        )
    )
    assert "Anti-ratchet" in text
    assert "ineligible" in text


def test_verify_qa_fail_hint_requires_eligible_blockers_only():
    LOOP = ROOT / "loop"
    if str(LOOP) not in sys.path:
        sys.path.insert(0, str(LOOP))
    from mb_finish.verify_hint import mb_finish_hint_after_verdict

    hint = mb_finish_hint_after_verdict("verify-qa", "FAIL", ROOT)
    assert hint is not None
    assert "eligible" in hint
    assert "style" in hint.lower()


def test_lean_qa_gates_anti_ratchet():
    text = (
        ROOT / "harness/cursor/rules/back_developer/isolation_rules/_lean/qa.mdc"
    ).read_text(encoding="utf-8")
    assert "Anti-ratchet (HARD)" in text
    assert "arm BUGFIX на style" in text
    assert "literal" in text and "plan AC" in text
