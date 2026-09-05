"""sync_cursor must not downgrade DONE; legacy REFLECT handoff is non-blocking (T-HUB-060)."""

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


def test_handoff_gate_phase_from_frontmatter_back_reflect() -> None:
    from loop.schemas.active_context import handoff_gate_phase_from_text

    text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: BACK REFLECT\n"
        "epic_id: T-HUB-043-runtime-bridge-codex\n"
        "---\n\n"
        "## Handoff BACK BACK REFLECT\n"
        "- **Дальше:** reflection\n"
    )
    assert handoff_gate_phase_from_text(text) is None


def test_sync_cursor_ignores_legacy_reflect_handoff_without_halt(tmp_path: Path) -> None:
    from epic import handoff_post_implement_phase, save_epic_state, sync_cursor_from_index

    epic = "T-HUB-043-runtime-bridge-codex"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s11\n"
        "  file: s11-legacy-purge.yaml\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / "memory-bank/back/audit" / epic / "audit-20260902-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: BACK REFLECT\n"
        f"epic_id: {epic}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        "## Handoff BACK BACK REFLECT\n"
        "- **Дальше:** reflection\n",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "s11",
        },
    )

    res = sync_cursor_from_index(tmp_path)
    assert res.get("halt") is not True, res
    # Legacy REFLECT handoff must not halt; sync may rewrite to lifecycle phase (QA/DONE).
    phase = handoff_post_implement_phase(
        (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    )
    assert phase in {None, "QA", "DONE", "AUDIT", "BUGFIX"}, phase


def test_sync_cursor_preserves_qa_handoff_without_rearm(tmp_path: Path) -> None:
    from epic import save_epic_state, sync_cursor_from_index

    epic = "T-HUB-demo"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / "memory-bank/back/audit" / epic / "audit-20260902-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    _write(
        tmp_path / f"memory-bank/back/events/{epic}/events.jsonl",
        '{"kind":"audit_done","seq":1,"epic_id":"'
        + epic
        + '","artifact":"memory-bank/back/audit/'
        + epic
        + '/audit-20260902-demo.yaml"}\n',
    )
    qa_body = (
        "## load_now\n"
        f"1. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff BACK QA — {epic}\n"
        "- **Режим/шаг:** `BACK QA`.\n"
    )
    _write(tmp_path / "memory-bank/activeContext.md", qa_body)
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "s01",
        },
    )

    res = sync_cursor_from_index(tmp_path)
    assert res.get("synced") is False
    assert res.get("reason") == "handoff_aligned"
    assert (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8") == qa_body


def test_prepare_completes_after_mb_finish_qa(tmp_path: Path) -> None:
    from epic import save_epic_state
    from loop.context_loop import prepare_session
    from loop.mb_finish.impl import finish_qa
    from loop.mb_finish.schemas import MbFinishRequest

    epic = "T-HUB-finish-qa"
    decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-one.yaml\n"
        "  status: completed\n",
    )
    qa_dir = tmp_path / "memory-bank/back/qa" / epic
    qa_dir.mkdir(parents=True)
    (qa_dir / "qa-20260902-demo.yaml").write_text("verdict: pass\n", encoding="utf-8")
    _write(
        tmp_path / "memory-bank/back/audit" / epic / "audit-20260902-demo.yaml",
        "schema: epic-audit/v1\n",
    )
    save_epic_state(
        tmp_path,
        {"armed_epic": epic, "armed_decompose": decompose, "armed_step": "QA", "role": "BACK"},
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        f"## Handoff BACK QA — {epic}\n",
    )

    finish = finish_qa(
        MbFinishRequest(
            phase="BACK QA",
            step_id="QA",
            done_summary="qa ok",
            cwd=str(tmp_path),
        )
    )
    assert finish.ok is True, finish
    assert finish.epic_done is True
    assert finish.next_phase == "DONE"

    prep = prepare_session(tmp_path)
    assert prep.get("complete") is True, prep
    assert prep.get("stop") == "EPIC_DONE"
