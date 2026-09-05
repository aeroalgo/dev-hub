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

    from harness.hooks._lib import current_gate_identity, verdict_evidence
    from harness.hooks.epic.core import mirror_gate_verdict
    ev = verdict_evidence(current_gate_identity(str(tmp_path), "test"), "PASS")
    ev["authority"] = "manual"
    mirror_gate_verdict(tmp_path, "PASS", evidence=ev)

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


def test_bugfix_cannot_finish_as_implement_or_handoff(tmp_path):
    from loop.mb_finish.impl import finish_handoff
    from loop.mb_finish.finish_implement import finish_implement_step
    from loop.mb_finish.schemas import MbFinishRequest, LoopHandoffMeta, HandoffBody
    _seed_epic(tmp_path, "T-finish-bugfix-guard")
    out = finish_implement_step(MbFinishRequest(cwd=str(tmp_path), phase="IMPLEMENT", step_id="s01", done_summary=""))
    assert "bugfix_finish_required" in out.diagnostic_codes
    out = finish_handoff(LoopHandoffMeta(role="BACK", mode="QA", epic_id="T-finish-bugfix-guard"), [], HandoffBody(mode="QA"), cwd=tmp_path)
    assert "bugfix_finish_required" in out.diagnostic_codes


def test_bugfix_rejects_missing_verifier_evidence(tmp_path):
    from loop.mb_finish.impl import finish_bugfix
    from loop.mb_finish.schemas import MbFinishRequest
    epic = "T-bugfix-gate"
    _seed_epic(tmp_path, epic)
    _write(tmp_path / f"memory-bank/back/bugfix/{epic}/bugfix-20260905-fix.md", "# root cause\nfixed\n")
    out = finish_bugfix(MbFinishRequest(cwd=str(tmp_path), phase="BUGFIX", step_id="BUGFIX", done_summary=""))
    assert not out.ok
    assert "verify_pass_missing" in out.diagnostic_codes


def test_qa_event_preserves_original_content(tmp_path):
    import json, hashlib
    from harness.hooks.epic.core import _append_event
    epic = "T-qa-history"
    p = tmp_path / f"memory-bank/back/qa/{epic}/qa-20260905-run1.yaml"
    original = "verdict: fail\nfix_plan: [fix boundary scanner]\n"
    _write(p, original)
    assert _append_event(tmp_path, "back", epic, "qa_fail", p)
    event = json.loads((tmp_path / f"memory-bank/back/events/{epic}/events.jsonl").read_text())
    snapshot = tmp_path / event["metadata"]["artifact_snapshot"]
    p.write_text("verdict: pass\n")
    assert snapshot.read_text() == original
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == event["artifact_sha256"]


def test_recorded_qa_write_is_denied_and_new_run_allowed(tmp_path):
    from harness.hooks._lib import active_context_write_deny_reason
    from harness.hooks.epic.core import _append_event
    epic = "T-qa-preserve"
    path = tmp_path / f"memory-bank/back/qa/{epic}/qa-20260905-run1.yaml"
    _write(path, "verdict: fail\n")
    _append_event(tmp_path, "back", epic, "qa_fail", path)
    assert "recorded_artifact_immutable" in (active_context_write_deny_reason(tmp_path, path, "verdict: pass\n") or "")
    assert active_context_write_deny_reason(tmp_path, path.with_name("qa-20260905-run2.yaml"), "verdict: pass\n") is None


def test_qa_finish_rejects_bugfix_phase(tmp_path):
    from loop.mb_finish.impl import finish_qa
    from loop.mb_finish.schemas import MbFinishRequest
    epic = "T-qa-no-bypass"
    _seed_epic(tmp_path, epic)
    out = finish_qa(MbFinishRequest(cwd=str(tmp_path), phase="QA", step_id="QA", done_summary=""))
    assert not out.ok
    assert "bugfix_finish_required" in out.diagnostic_codes
