from __future__ import annotations

from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
HOOKS = ROOT / "harness" / "hooks"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def test_extract_plan_checklist_hub_080():
    from qa_checklist_freeze import extract_plan_checklist, freeze_from_lists

    plan = (
        ROOT
        / "memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/plan.md"
    )
    text = plan.read_text(encoding="utf-8")
    plus, minus, sec, source = extract_plan_checklist(text)
    assert source in {"plan_ac", "qa_consumes"}
    assert len(plus) >= 8
    assert any("capability_checks" in x or "hub-only" in x for x in plus)
    assert len(minus) >= 5
    assert any("pytest" in x for x in minus)
    assert sec
    freeze = freeze_from_lists(
        epic_id="T-HUB-080-workflow-capability-instruction-parity",
        ac_plus=plus,
        ac_minus=minus,
        section_011=sec,
        source_path=str(plan),
        source=source,
    )
    assert freeze.checklist_sha256
    assert freeze.schema_version == "loop-qa-checklist-freeze/v1"


def test_ensure_freeze_persists_sha_stable(tmp_path: Path):
    from qa_checklist_freeze import ensure_freeze, load_freeze, persist_freeze

    epic = "T-HUB-080-workflow-capability-instruction-parity"
    mb = tmp_path / "memory-bank" / "back" / "plan" / epic / "md"
    mb.mkdir(parents=True)
    src = (
        ROOT
        / "memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/plan.md"
    )
    (mb / "plan.md").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    first = ensure_freeze(tmp_path, epic_id=epic, role="back", state={})
    assert first is not None
    state = persist_freeze({}, first)
    second = ensure_freeze(tmp_path, epic_id=epic, role="back", state=state)
    assert second is not None
    assert second.checklist_sha256 == first.checklist_sha256
    assert load_freeze(state) is not None


def test_render_freeze_prompt_includes_prior_blockers_and_classes():
    from qa_checklist_freeze import freeze_from_lists, render_freeze_prompt_block, with_prior_blockers

    freeze = freeze_from_lists(
        epic_id="T-demo",
        ac_plus=["AC one"],
        ac_minus=["no raw pytest"],
    )
    freeze = with_prior_blockers(freeze, ["prior_open: still open"])
    text = render_freeze_prompt_block(freeze, prior_only=True)
    assert "Frozen QA checklist" in text
    assert freeze.checklist_sha256 in text
    assert "AC one" in text
    assert "prior_open: still open" in text
    assert "verify_scope: `prior_only`" in text
    assert "suite_red" in text


def test_build_prompt_qa_includes_frozen_checklist():
    from context_loop import build_prompt

    text = build_prompt(
        ROOT,
        load_now=["memory-bank/activeContext.md"],
        projection={
            "phase": "BACK QA",
            "epic": "T-HUB-080-workflow-capability-instruction-parity",
            "next_step": "QA",
        },
    )
    assert "Frozen QA checklist" in text
    assert "checklist_sha256" in text
    assert "Prior blockers" in text
    assert "suite_red" in text


def test_spawn_freeze_violations_require_matching_sha():
    from qa_checklist_freeze import freeze_from_lists, persist_freeze, spawn_freeze_violations

    freeze = freeze_from_lists(
        epic_id="T-demo",
        ac_plus=["AC one"],
        ac_minus=["no raw pytest"],
    )
    state = persist_freeze({}, freeze)
    missing = spawn_freeze_violations("## AC+\n- AC one\n", state)
    assert any("checklist_sha256" in e for e in missing)
    ok_prompt = (
        f"## Frozen QA checklist\n- checklist_sha256: `{freeze.checklist_sha256}`\n"
        "### AC+\n- AC one\n### AC−\n- no raw pytest\n### §0.11\n"
        "- orphan external refs only (API/env/storage/event/DB counterparts); not style/naming/comments\n"
    )
    assert spawn_freeze_violations(ok_prompt, state) == []


def test_validate_blockers_require_eligible_class():
    from qa_checklist_freeze import freeze_from_lists, validate_blockers_against_freeze

    freeze = freeze_from_lists(epic_id="T", ac_plus=["A"], ac_minus=["B"])
    errs = validate_blockers_against_freeze(["style: rename p"], freeze)
    assert errs
    assert not validate_blockers_against_freeze(["suite_red: 2 tests failed"], freeze)


def test_finish_qa_freeze_errors_on_unclassed_blockers(tmp_path: Path):
    from qa_checklist_freeze import finish_qa_freeze_errors, freeze_from_lists

    qa = tmp_path / "qa.yaml"
    qa.write_text(
        "schema: epic-qa/v1\nrole: back\ndate: 2026-09-10\nreviewer: x\n"
        "verdict: fail\nchecks: [a]\nblockers:\n  - bad style\nfix_plan: [x]\n",
        encoding="utf-8",
    )
    freeze = freeze_from_lists(epic_id="T", ac_plus=["A"], ac_minus=["B"])
    errs = finish_qa_freeze_errors(path=qa, freeze=freeze, verdict="fail")
    assert any("eligible class" in e for e in errs)


def test_epic_qa_yaml_requires_blocker_class():
    from epic_shard_extra import validate_qa_yaml

    path = ROOT / "loop/tests/_tmp_qa_class.yaml"
    path.write_text(
        "schema: epic-qa/v1\nrole: back\ndate: '2026-09-10'\nreviewer: x\n"
        "verdict: fail\nscope: [s]\nchecks: [c]\nblockers: ['no class']\n"
        "fix_plan:\n  - issue: i\n    command: BACK BUGFIX\n    subject: s\n",
        encoding="utf-8",
    )
    try:
        errs = validate_qa_yaml(path)
        assert any("eligible class" in e for e in errs), errs
    finally:
        path.unlink(missing_ok=True)


def test_front_integ_lean_qa_mention_freeze():
    front = (
        ROOT / "harness/cursor/rules/front_developer/isolation_rules/_lean/qa.mdc"
    ).read_text(encoding="utf-8")
    integ = (
        ROOT / "harness/cursor/rules/integration_developer/isolation_rules/_lean/qa.mdc"
    ).read_text(encoding="utf-8")
    assert "checklist_sha256" in front and "prior_only" in front
    assert "checklist_sha256" in integ and "prior_only" in integ
