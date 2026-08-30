"""Handoff SoT vs auto-reconciled post-implement lifecycle."""

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


def _load_ctx():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("context_loop_handoff", LOOP / "context_loop.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_handoff_reflect_blocks_epic_done_despite_stale_reflection(tmp_path: Path) -> None:
    from epic import epic_complete_allowed, handoff_post_implement_phase, reduce_epic_lifecycle

    epic = "T-059-bot-graph-test-harness"
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
    qa = tmp_path / f"memory-bank/back/qa/{epic}/qa-20260830-bot-graph-test-harness.yaml"
    refl = tmp_path / f"memory-bank/back/reflection/reflection-{epic}.md"
    _write(qa, "schema: epic-qa/v1\nverdict: pass\nissues: []\n")
    _write(
        refl,
        "---\n"
        f"epic_id: {epic}\n"
        "date: '2026-08-29'\n"
        "---\n\n"
        "# old reflection\n",
    )
    qa.touch()
    import os
    import time

    old = qa.stat().st_mtime
    os.utime(refl, (old - 3600, old - 3600))
    time.sleep(0.01)

    handoff_text = (
        "## load_now\n"
        f"1. [qa](back/qa/{epic}/qa-20260830-bot-graph-test-harness.yaml)\n\n"
        f"## Handoff BACK REFLECT — {epic}\n"
        "- **Режим/шаг:** `BACK REFLECT`.\n"
        "- **Дальше:** reflection-*.md.\n"
    )
    _write(tmp_path / "memory-bank/activeContext.md", handoff_text)
    assert handoff_post_implement_phase(handoff_text) == "REFLECT"

    gate = epic_complete_allowed(tmp_path)
    assert gate.get("allowed") is False
    assert gate.get("phase") == "REFLECT"

    decision = reduce_epic_lifecycle(tmp_path, "back", epic)
    assert decision.get("phase") == "REFLECT"
    assert decision.get("reason_code") in {
        "qa_passed",
        "qa_passed_stale_reflection",
    }


def test_prepare_skips_epic_done_when_handoff_reflect(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    epic = "demo"
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
        tmp_path / f"memory-bank/back/plan/decompose-{epic}/s01-one.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\n",
    )
    _write(
        tmp_path / f"memory-bank/back/implement/implement-{epic}/s01-one.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\n"
        f"plan_id: {epic}\ntitle: s01 — one IMPLEMENT\nstatus: completed\n"
        f"decompose_ref: memory-bank/back/plan/decompose-{epic}/s01-one.yaml\n"
        "date: '2026-08-29'\n",
    )
    _write(
        tmp_path / f"memory-bank/back/qa/{epic}/qa-20260829-demo.yaml",
        "schema: epic-qa/v1\nverdict: pass\nissues: []\n",
    )
    _write(
        tmp_path / f"memory-bank/back/reflection/reflection-{epic}.md",
        f"---\nepic_id: {epic}\n---\n# reflection\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n1. x\n\n"
        f"## Handoff BACK REFLECT — {epic}\n"
        "- **Режим/шаг:** `BACK REFLECT`.\n",
    )
    from epic import load_epic_state, save_epic_state

    st = load_epic_state(tmp_path)
    st.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "QA",
            "role": "BACK",
        }
    )
    save_epic_state(tmp_path, st)

    out = ctx.prepare_session(tmp_path)
    assert out.get("complete") is not True, out
    assert out.get("stop") != "EPIC_DONE"
    assert out.get("ok") is True


def test_mb_paths_for_prompt_are_absolute(tmp_path: Path) -> None:
    ctx = _load_ctx()
    ac = tmp_path / "memory-bank/activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text("## load_now\n", encoding="utf-8")
    plan = tmp_path / "memory-bank/back/plan/plan-demo.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# plan\n", encoding="utf-8")
    paths = ctx.mb_paths_for_prompt(
        tmp_path,
        ["memory-bank/back/plan/plan-demo.md"],
    )
    assert paths[0] == str(ac.resolve())
    assert paths[1] == str(plan.resolve())


def test_projection_from_state_when_no_decompose_index(tmp_path: Path) -> None:
    from epic import load_epic_state, rebuild_epic_projection, save_epic_state

    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n- [plan](back/plan/plan-T-060.md)\n\n"
        "## Handoff BACK DECOMPOSE — T-060\n",
    )
    st = load_epic_state(tmp_path)
    st.update(
        {
            "armed_epic": "T-060",
            "armed_step": "DECOMPOSE",
            "role": "BACK",
            "armed_decompose": None,
        }
    )
    save_epic_state(tmp_path, st)
    projection = rebuild_epic_projection(tmp_path)
    proj = projection.get("projection") or {}
    assert proj.get("epic") == "T-060"
    assert proj.get("phase") == "DECOMPOSE"
    assert proj.get("next_step") == "DECOMPOSE"
