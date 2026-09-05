from pathlib import Path

from harness.hooks.epic.core import (
    _append_event,
    load_epic_state,
    mirror_gate_verdict,
    mirror_verify_verdict,
    reconcile_epic_events,
    reduce_epic_lifecycle,
    save_epic_state,
)


def test_reducer_keeps_qa_open_until_post_bugfix_run_finishes(tmp_path: Path):
    epic = "demo"
    qa = tmp_path / "memory-bank/back/qa/demo/qa-old.yaml"
    qa.parent.mkdir(parents=True)
    qa.write_text("verdict: pass\nepic_id: demo\n")
    _append_event(tmp_path, "back", epic, "qa_pass", qa)
    bugfix = tmp_path / "memory-bank/back/bugfix/demo/bugfix-001.md"
    bugfix.parent.mkdir(parents=True)
    bugfix.write_text("fixed\n")
    _append_event(tmp_path, "back", epic, "bugfix_done", bugfix)
    save_epic_state(tmp_path, {
        "armed_epic": epic,
        "armed_role": "BACK",
        "qa_after_bugfix": {
            "epic_id": epic,
            "phase_run_id": "bugfix-run",
            "existing_artifacts": ["memory-bank/back/qa/demo/qa-old.yaml"],
        },
    })
    assert reduce_epic_lifecycle(tmp_path, "back", epic)["phase"] == "QA"
from loop.mb_finish.impl import finish_bugfix, finish_qa
from loop.mb_finish.schemas import MbFinishRequest


def test_draft_qa_pass_cannot_complete_epic(tmp_path: Path):
    qa = tmp_path / "memory-bank/back/qa/demo/qa-premature.yaml"
    qa.parent.mkdir(parents=True)
    qa.write_text("verdict: pass\nepic_id: demo\n")

    events = reconcile_epic_events(tmp_path, "back", "demo")

    assert not any(event["kind"] == "qa_pass" for event in events)
    assert reduce_epic_lifecycle(tmp_path, "back", "demo")["phase"] != "DONE"


def _request(tmp_path: Path, phase: str):
    return MbFinishRequest(phase=phase, step_id=phase, done_summary="", cwd=str(tmp_path))


def _begin_bugfix(tmp_path: Path):
    qa = tmp_path / "memory-bank/back/qa/demo/qa-001.yaml"
    qa.parent.mkdir(parents=True)
    qa.write_text("verdict: fail\nepic_id: demo\n")
    save_epic_state(tmp_path, {"armed_epic": "demo", "armed_role": "BACK", "phase": "QA", "session_id": "runner", "phase_run_id": "initial-qa"})
    assert finish_qa(_request(tmp_path, "QA")).ok
    st = load_epic_state(tmp_path)
    st["phase_run_id"] = "bugfix-session"
    save_epic_state(tmp_path, st)
    mirror_verify_verdict(tmp_path, "PASS", evidence={"authority": "manual", "step": "BUGFIX", "session_id": "bugfix-session"})
    bugfix = tmp_path / "memory-bank/back/bugfix/demo/bugfix-001.md"
    bugfix.parent.mkdir(parents=True)
    bugfix.write_text("# Fixed\nRoot cause removed.\n")
    return qa


def test_bugfix_requires_new_qa_session_and_new_artifact(tmp_path: Path):
    _begin_bugfix(tmp_path)
    premature = tmp_path / "memory-bank/back/qa/demo/qa-002.yaml"
    premature.write_text("verdict: pass\nepic_id: demo\n")
    reconcile_epic_events(tmp_path, "back", "demo")
    assert finish_bugfix(_request(tmp_path, "BUGFIX")).ok
    assert reduce_epic_lifecycle(tmp_path, "back", "demo")["phase"] == "QA"

    same_session = finish_qa(_request(tmp_path, "QA"))
    assert not same_session.ok
    assert "qa_new_session_required" in same_session.diagnostic_codes

    st = load_epic_state(tmp_path)
    st["phase_run_id"] = "qa-rerun"
    save_epic_state(tmp_path, st)
    old_artifact = finish_qa(_request(tmp_path, "QA"))
    assert not old_artifact.ok
    assert "qa_new_artifact_required" in old_artifact.diagnostic_codes

    fresh = premature.with_name("qa-003.yaml")
    fresh.write_text("verdict: pass\nepic_id: demo\nchecks: [rerun]\n")
    unreviewed = finish_qa(_request(tmp_path, "QA"))
    assert not unreviewed.ok
    assert "qa_reviewer_required" in unreviewed.diagnostic_codes
    mirror_gate_verdict(tmp_path, "PASS", agent_id="reviewer", evidence={
        "authority": "manual", "step": "QA", "session_id": "qa-rerun",
    })
    result = finish_qa(_request(tmp_path, "QA"))
    assert result.ok, result
    assert result.epic_done
    assert reduce_epic_lifecycle(tmp_path, "back", "demo")["phase"] == "DONE"


def test_reviewer_verdict_cannot_replace_bugfix_verification(tmp_path: Path):
    _begin_bugfix(tmp_path)
    mirror_gate_verdict(tmp_path, "PASS", agent_id="reviewer", evidence={
        "authority": "manual", "step": "QA", "session_id": "bugfix-session",
    })
    st = load_epic_state(tmp_path)
    assert st["last_verify_evidence"]["step"] == "BUGFIX"
    assert st["last_reviewer_evidence"]["step"] == "QA"


def test_rebinding_evidence_step_cannot_authorize_bugfix(tmp_path: Path):
    _begin_bugfix(tmp_path)
    mirror_verify_verdict(tmp_path, "PASS", evidence={"authority": "manual", "step": "QA"})
    st = load_epic_state(tmp_path)
    st["last_verify_evidence"]["step"] = "BUGFIX"
    save_epic_state(tmp_path, st)
    result = finish_bugfix(_request(tmp_path, "BUGFIX"))
    assert not result.ok
    assert "verdict_evidence_modified" in result.diagnostic_codes
