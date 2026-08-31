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
    from loop.schemas.active_context import handoff_mode_from_text, parse_handoff_meta

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
        "- **Режим/шаг:** `BACK BUGFIX`.\n"
    )
    meta = parse_handoff_meta(text)
    assert meta is not None
    assert meta.mode == "REFLECT"
    assert handoff_mode_from_text(text) == "REFLECT"


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
    assert out.get("phase") == "REFLECT", out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "schema: loop-handoff/v1" in ac
    assert handoff_post_implement_phase(ac) == "REFLECT"


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
