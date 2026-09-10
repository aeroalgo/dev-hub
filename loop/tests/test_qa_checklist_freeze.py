from __future__ import annotations

from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"
if str(LOOP) not in sys.path:
    sys.path.insert(0, str(LOOP))


def test_extract_plan_checklist_hub_080():
    from qa_checklist_freeze import extract_plan_checklist, freeze_from_lists

    plan = (
        ROOT
        / "memory-bank/back/plan/T-HUB-080-workflow-capability-instruction-parity/md/plan.md"
    )
    text = plan.read_text(encoding="utf-8")
    plus, minus, sec = extract_plan_checklist(text)
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


def test_render_freeze_prompt_includes_prior_blockers():
    from qa_checklist_freeze import freeze_from_lists, render_freeze_prompt_block, with_prior_blockers

    freeze = freeze_from_lists(
        epic_id="T-demo",
        ac_plus=["AC one"],
        ac_minus=["no raw pytest"],
    )
    freeze = with_prior_blockers(freeze, ["B1: still open"])
    text = render_freeze_prompt_block(freeze)
    assert "Frozen QA checklist" in text
    assert freeze.checklist_sha256 in text
    assert "AC one" in text
    assert "B1: still open" in text
    assert "FORBIDDEN" in text


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
