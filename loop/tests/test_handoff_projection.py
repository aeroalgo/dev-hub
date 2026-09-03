"""Typed handoff frontmatter + reducer projection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
LOOP = ROOT / "loop"
for p in (str(HOOKS), str(LOOP)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_handoff_frontmatter_parse_and_mode(tmp_path: Path) -> None:
    from loop.schemas.active_context import (
        handoff_gate_phase_from_text,
        handoff_mode_from_text,
        parse_handoff_meta,
    )

    text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: REFLECT\n"
        "epic_id: demo\n"
        "---\n\n"
        "## load_now\n"
        "- qa.yaml\n\n"
        "## Handoff BACK REFLECT — demo\n"
        "- **Дальше:** выполнить REFLECT.\n"
    )
    meta = parse_handoff_meta(text)
    assert meta is not None
    assert meta.mode == "REFLECT"
    assert handoff_mode_from_text(text) == "REFLECT"
    assert handoff_gate_phase_from_text(text) == "REFLECT"


def test_handoff_mode_back_reflect_normalizes(tmp_path: Path) -> None:
    from loop.schemas.active_context import handoff_gate_phase_from_text, handoff_mode_from_text

    text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: BACK REFLECT\n"
        "epic_id: demo\n"
        "---\n\n"
        "## Handoff BACK BACK REFLECT\n"
    )
    assert handoff_mode_from_text(text) == "REFLECT"
    assert handoff_gate_phase_from_text(text) == "REFLECT"


def test_project_handoff_from_reducer_syncs_stale_markdown(tmp_path: Path) -> None:
    from epic import project_handoff_from_reducer, handoff_post_implement_phase

    epic = "T-proj-demo"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / f"memory-bank/back/qa/{epic}/qa-20260830-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n"
        f"1. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff BACK BUGFIX — {epic}\n"
        "- **Режим/шаг:** `BACK BUGFIX`.\n",
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("ok") is True, out
    assert out.get("projected") is True, out
    assert out.get("phase") == "DONE", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "DONE" in ac or "EPIC_DONE" in ac
    assert "Handoff BACK DONE" in ac or "mode: DONE" in ac or "BACK DONE" in ac
    assert handoff_post_implement_phase(ac) is None or "DONE" in ac


def test_gate_verdict_sidecar_preferred_over_regex(tmp_path: Path) -> None:
    from loop.gate_verdict_store import write_gate_verdict
    from _lib import extract_verdict

    write_gate_verdict(
        tmp_path,
        "verify",
        "PASS",
        step_id="s01",
        session_id="sess-1",
        epic_id="demo",
        recorded_at="2026-08-30T12:00:00Z",
    )
    verdict = extract_verdict("VERDICT: FAIL\n", cwd=str(tmp_path), agent_id="verify")
    assert verdict == "PASS"


def test_epic_complete_allowed_uses_reducer_not_stale_handoff(tmp_path: Path) -> None:
    from epic import epic_complete_allowed, reduce_epic_lifecycle

    epic = "T-done-demo"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / f"memory-bank/back/qa/{epic}/qa-20260830-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path / f"memory-bank/back/reflection/reflection-{epic}.md",
        "---\n"
        f"epic_id: {epic}\n"
        "date: '2026-08-30'\n"
        "---\n\n"
        "# reflection\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n"
        f"1. [qa](back/qa/{epic}/qa-20260830-demo.yaml)\n\n"
        f"## Handoff BACK REFLECT — {epic}\n"
        "- **Режим/шаг:** `BACK REFLECT`.\n",
    )

    decision = reduce_epic_lifecycle(tmp_path, "back", epic)
    assert decision.get("phase") == "DONE"

    gate = epic_complete_allowed(tmp_path)
    assert gate.get("allowed") is True, gate


def test_handoff_mode_line_wins_over_stale_audit_heading() -> None:
    from epic import handoff_post_implement_phase

    text = (
        "## load_now\n"
        "1. [index.yaml](back/plan/decompose-demo/index.yaml)\n\n"
        "## Handoff BACK AUDIT — demo\n"
        "- **Режим/шаг:** `BACK QA`.\n"
        "- **Дальше:** переход к `BACK QA`.\n"
    )
    assert handoff_post_implement_phase(text) == "QA"


def test_handoff_qa_not_demoted_by_dalshe_reflect() -> None:
    from epic import handoff_post_implement_phase

    text = (
        "## load_now\n"
        "1. [index.yaml](back/plan/decompose-T-HUB-040/index.yaml)\n\n"
        "## Handoff BACK QA — T-HUB-040\n"
        "- **Эпик:** T-HUB-040 — все sNN completed.\n"
        "- **Режим/шаг:** `BACK QA`.\n"
        "- **Дальше:** выполнить `BACK QA`; в Handoff следующий = `BACK REFLECT`.\n"
    )
    assert handoff_post_implement_phase(text) == "QA"


def test_project_handoff_from_reducer_syncs_stale_audit_to_qa(tmp_path: Path) -> None:
    from epic import handoff_post_implement_phase, project_handoff_from_reducer

    epic = "T-audit-qa-demo"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    audit = f"memory-bank/back/audit/{epic}/audit-20260902-demo.yaml"
    events = f"memory-bank/back/events/{epic}/events.jsonl"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(tmp_path / audit, "not_implemented: []\nqa_ready: true\n")
    _write(
        tmp_path / events,
        '{"schema":"loop-event/v2","seq":1,"kind":"audit_done","artifact":"'
        + audit
        + '","epic_id":"'
        + epic
        + '"}\n',
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: AUDIT\n"
        f"epic_id: {epic}\n"
        "step_id: AUDIT\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decompose}]({decompose})\n\n"
        f"## Handoff BACK AUDIT — {epic}\n"
        "- **Режим/шаг:** `BACK QA`.\n",
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("projected") is True, out
    assert out.get("phase") == "QA", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: QA" in ac
    assert "## Handoff BACK QA" in ac
    assert handoff_post_implement_phase(ac) == "QA"


def test_project_handoff_from_reducer_qa_failed_stays_bugfix(
    tmp_path: Path,
) -> None:
    from epic import handoff_post_implement_phase, project_handoff_from_reducer

    epic = "T-qa-fail-bugfix"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    audit = f"memory-bank/back/audit/{epic}/audit-20260902-demo.yaml"
    qa = f"memory-bank/back/qa/{epic}/qa-20260902-demo.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(tmp_path / audit, "not_implemented: []\nqa_ready: true\n")
    _write(tmp_path / qa, "schema: epic-qa/v1\nverdict: fail\nissues: []\n")
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: AUDIT\n"
        f"epic_id: {epic}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decompose}]({decompose})\n\n"
        f"## Handoff BACK AUDIT — {epic}\n"
        "- **Дальше:** `BACK AUDIT`.\n",
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("projected") is True, out
    assert out.get("phase") == "BUGFIX", out
    assert out.get("reason_code") == "qa_failed", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: BUGFIX" in ac
    assert "## Handoff BACK BUGFIX" in ac
    assert handoff_post_implement_phase(ac) == "BUGFIX"


def test_project_handoff_from_reducer_qa_failed_rewrites_premature_qa(
    tmp_path: Path,
) -> None:
    from epic import handoff_post_implement_phase, project_handoff_from_reducer

    epic = "T-qa-fail-premature-qa"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    audit = f"memory-bank/back/audit/{epic}/audit-20260902-demo.yaml"
    qa = f"memory-bank/back/qa/{epic}/qa-20260902-demo.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(tmp_path / audit, "not_implemented: []\nqa_ready: true\n")
    _write(tmp_path / qa, "schema: epic-qa/v1\nverdict: fail\nissues: []\n")
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        f"epic_id: {epic}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decompose}]({decompose})\n\n"
        f"## Handoff BACK QA — {epic}\n"
        "- **Фаза:** BUGFIX завершена.\n"
        "- **Дальше:** `BACK QA`.\n",
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("projected") is True, out
    assert out.get("phase") == "BUGFIX", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: BUGFIX" in ac
    assert "## Handoff BACK BUGFIX" in ac
    assert handoff_post_implement_phase(ac) == "BUGFIX"


def test_project_handoff_from_reducer_skips_done_when_disabled(tmp_path: Path) -> None:
    from epic import project_handoff_from_reducer

    epic = "T-done-skip-demo"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / f"memory-bank/back/qa/{epic}/qa-20260830-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path / f"memory-bank/back/reflection/reflection-{epic}.md",
        "---\n"
        f"epic_id: {epic}\n"
        "date: '2026-08-30'\n"
        "---\n\n"
        "# reflection\n",
    )
    ac_path = tmp_path / "memory-bank/activeContext.md"
    _write(
        ac_path,
        "## load_now\n"
        f"1. [qa](back/qa/{epic}/qa-20260830-demo.yaml)\n\n"
        f"## Handoff BACK REFLECT — {epic}\n"
        "- **Режим/шаг:** `BACK REFLECT`.\n",
    )

    out = project_handoff_from_reducer(tmp_path, allow_terminal_done_projection=False)
    assert out.get("ok") is True, out
    assert out.get("phase") == "DONE", out
    assert out.get("projected") is False, out

    ac = ac_path.read_text(encoding="utf-8")
    assert "Handoff BACK REFLECT" in ac
    assert "Handoff BACK DONE" not in ac

    out_enabled = project_handoff_from_reducer(tmp_path, allow_terminal_done_projection=True)
    assert out_enabled.get("projected") is True, out_enabled
    ac_done = ac_path.read_text(encoding="utf-8")
    assert "Handoff BACK DONE" in ac_done


def test_project_handoff_implement_to_audit_when_queue_done(tmp_path: Path) -> None:
    from epic import handoff_post_implement_phase, project_handoff_from_reducer

    epic = "T-implement-to-audit"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        f"epic_id: {epic}\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decompose}]({decompose})\n\n"
        f"## Handoff BACK IMPLEMENT — {epic}\n"
        "- **Режим/шаг:** `BACK IMPLEMENT s01`.\n"
        "- NEED_HUMAN: verify_no_verdict\n",
    )

    out = project_handoff_from_reducer(tmp_path)
    assert out.get("projected") is True, out
    assert out.get("phase") == "AUDIT", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: AUDIT" in ac
    assert "## Handoff BACK AUDIT" in ac
    assert "verify_no_verdict" not in ac
    assert handoff_post_implement_phase(ac) == "AUDIT"


def test_clear_stale_verify_no_verdict_at_audit(tmp_path: Path) -> None:
    from epic import clear_stale_verify_no_verdict_handoff, load_epic_state, save_epic_state

    epic = "T-stale-verify-audit"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  title: one\n"
        "  status: completed\n",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "AUDIT",
            "role": "BACK",
        },
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: AUDIT\n"
        f"epic_id: {epic}\n"
        f"step_id: {epic}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decompose}]({decompose})\n\n"
        f"## Handoff BACK AUDIT — {epic}\n"
        "- **Режим/шаг:** `BACK AUDIT`.\n"
        "- **NEED_HUMAN:** verify_no_verdict\n",
    )

    out = clear_stale_verify_no_verdict_handoff(tmp_path)
    assert out.get("cleared") is True, out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "verify_no_verdict" not in ac

    ctx = __import__("loop.context_loop", fromlist=["prepare_session"])
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True
    assert not (prep.get("stop") or "").startswith("NEED_HUMAN")
