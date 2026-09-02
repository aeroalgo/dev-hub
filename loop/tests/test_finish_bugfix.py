"""finish_bugfix requires bugfix-*.md and emits bugfix_done before QA."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
LOOP = ROOT / "loop"
for p in (str(HOOKS), str(LOOP), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_epic(tmp_path: Path, epic: str) -> None:
    from epic import default_state, save_epic_state

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
        tmp_path / f"memory-bank/back/audit/{epic}/audit-20260902-demo.yaml",
        "not_implemented: []\nqa_ready: true\n",
    )
    _write(
        tmp_path / f"memory-bank/back/qa/{epic}/qa-20260902-demo.yaml",
        "schema: epic-qa/v1\nverdict: fail\nissues: []\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: BUGFIX\n"
        f"epic_id: {epic}\n"
        "---\n\n"
        f"## Handoff BACK BUGFIX — {epic}\n"
        "- **Дальше:** `BACK BUGFIX`.\n",
    )
    st = default_state()
    st["armed_epic"] = epic
    st["armed_role"] = "BACK"
    st["armed_decompose"] = decompose
    st["armed_step"] = "BUGFIX"
    st["phase"] = "BUGFIX"
    st["active"] = True
    st["status"] = "running"
    save_epic_state(tmp_path, st)


def test_finish_bugfix_fails_without_artifact(tmp_path: Path) -> None:
    from loop.mb_finish.impl import finish_bugfix
    from loop.mb_finish.schemas import MbFinishRequest

    epic = "T-finish-bugfix-missing"
    _seed_epic(tmp_path, epic)

    out = finish_bugfix(
        MbFinishRequest(
            cwd=str(tmp_path),
            phase="BUGFIX",
            step_id="BUGFIX",
            done_summary="missing artifact",
        )
    )
    assert out.ok is False
    assert "bugfix_artifact_missing" in (out.diagnostic_codes or [])


def test_finish_bugfix_requires_artifact_then_arms_qa(tmp_path: Path) -> None:
    from epic import load_epic_state, reduce_epic_lifecycle
    from loop.mb_finish.impl import finish_bugfix
    from loop.mb_finish.schemas import MbFinishRequest

    epic = "T-finish-bugfix-ok"
    _seed_epic(tmp_path, epic)
    # Materialize qa_fail in the event stream before the bugfix artifact,
    # matching real loop order (QA fail → BUGFIX work → bugfix-*.md).
    failed = reduce_epic_lifecycle(tmp_path, "back", epic)
    assert failed["reason_code"] == "qa_failed"

    _write(
        tmp_path / f"memory-bank/back/bugfix/{epic}/bugfix-20260902-demo.md",
        f"# bugfix\nepic_id: {epic}\n\nfixed suite regressions\n",
    )

    out = finish_bugfix(
        MbFinishRequest(
            cwd=str(tmp_path),
            phase="BUGFIX",
            step_id="BUGFIX",
            done_summary="bugfix done",
        )
    )
    assert out.ok is True, out

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: QA" in ac
    assert "Handoff BACK QA" in ac or "## Handoff BACK QA" in ac

    st = load_epic_state(tmp_path)
    assert st.get("armed_step") == "QA"
    assert st.get("phase") == "QA"

    decision = reduce_epic_lifecycle(tmp_path, "back", epic)
    assert decision["reason_code"] == "bugfix_reopens_qa"
    assert decision["phase"] == "QA"
    assert decision["last_event"]["kind"] == "bugfix_done"


def test_prepare_session_keeps_bugfix_when_qa_failed(
    tmp_path: Path,
) -> None:
    import loop.context_loop as ctx
    from epic import load_epic_state

    epic = "T-prepare-qa-failed"
    _seed_epic(tmp_path, epic)

    _write(
        tmp_path / "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        f"epic_id: {epic}\n"
        "---\n\n"
        "## load_now\n"
        f"1. [index.yaml](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff BACK QA — {epic}\n"
        "- **Фаза:** BUGFIX завершена.\n"
        "- **Дальше:** `BACK QA`.\n",
    )

    prep = ctx.prepare_session(tmp_path, model="gpt")
    assert prep.get("ok") is True, prep

    st = load_epic_state(tmp_path)
    assert st.get("armed_step") == "BUGFIX"
    assert st.get("phase") == "BUGFIX"

    ac = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    assert "mode: BUGFIX" in ac
    assert "Handoff BACK BUGFIX" in ac
