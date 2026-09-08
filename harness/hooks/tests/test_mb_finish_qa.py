"""Tests for finish_qa and finish_bugfix (s05 / TM-006)."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.hooks.epic.core import read_active_context, save_epic_state
from loop.mb_finish.impl import finish_bugfix, finish_qa
from loop.mb_finish.schemas import MbFinishRequest


def test_finish_qa_no_artifact(tmp_path: Path):
    """cp2: finish_qa without qa artifact returns ok=False and does not write activeContext."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa complete",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_artifact_missing" in res.diagnostic_codes
    assert not (mb_dir / "activeContext.md").exists()


def test_finish_qa_happy(tmp_path: Path):
    """cp1: finish_qa happy path with valid QA artifact -> ok=True, activeContext mode=DONE."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa passed successfully",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: DONE" in written
    assert "## Handoff BACK DONE" in written

    events = (
        tmp_path / "memory-bank" / "back" / "events" / "T-HUB-040" / "events.jsonl"
    )
    assert events.is_file()
    assert any(
        '"kind": "qa_pass"' in line or '"kind":"qa_pass"' in line
        for line in events.read_text(encoding="utf-8").splitlines()
    )


def test_finish_qa_active_run_requires_verify_qa_receipt(tmp_path: Path):
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-001.yaml").write_text(
        "verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8"
    )

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
            "active": True,
            "phase": "QA",
            "phase_run_id": "qa-run-1",
        },
    )

    result = finish_qa(
        MbFinishRequest(
            phase="BACK QA",
            step_id="QA",
            done_summary="qa passed without gate receipt",
            cwd=str(tmp_path),
        )
    )

    assert result.ok is False
    assert "qa_reviewer_required" in result.diagnostic_codes


def test_finish_qa_v2_layout_path_emits_qa_pass(tmp_path: Path):
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa.yaml").write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")
    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    res = finish_qa(
        MbFinishRequest(
            phase="BACK QA",
            step_id="s05",
            done_summary="qa v2",
            cwd=str(tmp_path),
        )
    )
    assert res.ok is True, res.diagnostic_codes
    events = tmp_path / "memory-bank" / "back" / "events" / "T-HUB-040" / "events.jsonl"
    body = events.read_text(encoding="utf-8")
    assert "qa_pass" in body
    assert "qa/T-HUB-040/qa.yaml" in body
    assert "yaml/qa.yaml" not in body


def test_finish_qa_handoff(tmp_path: Path):
    """cp3 / TM-006: finish_qa results in DONE handoff in activeContext."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa verified",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is True

    written = read_active_context(tmp_path)
    assert "mode: DONE" in written
    assert "## Handoff BACK DONE" in written


def test_finish_qa_fails_closed_when_lifecycle_event_cannot_be_recorded(tmp_path: Path):
    """QA must not report DONE when the durable qa_pass event was rejected."""
    epic = "T-HUB-040"
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / epic
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-001.yaml").write_text(
        "verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8"
    )

    events_dir = tmp_path / "memory-bank" / "back" / "events" / epic
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "events.jsonl").write_text(
        '{"kind":"not-a-valid-event","artifact":"memory-bank/x"}\n',
        encoding="utf-8",
    )

    active_context = tmp_path / "memory-bank" / "activeContext.md"
    active_context.parent.mkdir(parents=True, exist_ok=True)
    active_context.write_text("before QA finish\n", encoding="utf-8")
    save_epic_state(tmp_path, {"armed_epic": epic, "armed_role": "BACK"})

    res = finish_qa(
        MbFinishRequest(
            phase="BACK QA",
            step_id="QA",
            done_summary="qa passed",
            cwd=str(tmp_path),
        )
    )

    assert res.ok is False
    assert "qa_event_persist_failed" in res.diagnostic_codes
    assert res.epic_done is None
    assert active_context.read_text(encoding="utf-8") == "before QA finish\n"


def test_finish_bugfix_happy(tmp_path: Path):
    """cp4: finish_bugfix happy path with valid bugfix artifact -> ok=True."""
    bugfix_dir = tmp_path / "memory-bank" / "back" / "bugfix" / "T-HUB-040"
    bugfix_dir.mkdir(parents=True, exist_ok=True)
    (bugfix_dir / "bugfix-001.md").write_text(
        "# Bugfix\n\nRoot cause fixed.\n",
        encoding="utf-8",
    )

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK BUGFIX",
        step_id="s01",
        done_summary="bugfix applied",
        cwd=str(tmp_path),
    )
    res = finish_bugfix(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: QA" in written
    assert "## Handoff BACK QA" in written


def test_finish_bugfix_fail_closed(tmp_path: Path):
    """cp4: finish_bugfix without decompose shard fails closed."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK BUGFIX",
        step_id="s01",
        done_summary="bugfix applied",
        cwd=str(tmp_path),
    )
    res = finish_bugfix(req)
    assert res.ok is False
    assert "bugfix_artifact_missing" in res.diagnostic_codes


import pytest

@pytest.mark.parametrize("verdict", ["fail", "blocked"])
def test_finish_qa_verdict_fail_or_blocked_routes_to_bugfix_not_done(tmp_path: Path, verdict: str):
    """cp1 / US-001 / SC-001: verdict fail/blocked -> next_mode BUGFIX, not DONE / not EPIC_DONE."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text(f"verdict: {verdict}\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa found blockers",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: BUGFIX" in written
    assert "## Handoff BACK BUGFIX" in written
    assert "mode: DONE" not in written
    assert "EPIC_DONE" not in written

    st = save_epic_state  # state check
    from harness.hooks.epic.core import load_epic_state
    st_loaded = load_epic_state(tmp_path)
    assert st_loaded.get("phase") != "DONE"


def test_finish_qa_after_bugfix_reuses_same_yaml_fails(tmp_path: Path):
    """cp2 / US-002 / SC-002: after finish_bugfix, reusing earlier qa fail yaml is rejected."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-20260905-fail.yaml"
    qa_file.write_text("verdict: fail\nepic_id: T-HUB-040\n", encoding="utf-8")

    # Simulate QaAfterBugfix recorded by finish_bugfix
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
            "phase_run_id": "session-run-2",
            "qa_after_bugfix": {
                "epic_id": "T-HUB-040",
                "phase_run_id": "session-run-1",
                "existing_artifacts": ["memory-bank/back/qa/T-HUB-040/qa-20260905-fail.yaml"],
            },
        },
    )

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="re-qa attempted without new yaml",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_new_artifact_required" in res.diagnostic_codes


def test_finish_qa_after_bugfix_same_session_fails(tmp_path: Path):
    """cp2 / TM-005: after finish_bugfix, finishing QA in same session fails with qa_new_session_required."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-20260905-new.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
            "phase_run_id": "session-run-1",
            "qa_after_bugfix": {
                "epic_id": "T-HUB-040",
                "phase_run_id": "session-run-1",
                "existing_artifacts": ["memory-bank/back/qa/T-HUB-040/qa-20260905-fail.yaml"],
            },
        },
    )

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="re-qa in same session",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_new_session_required" in res.diagnostic_codes


def test_finish_qa_parse_qa_verdict_missing_does_not_route_to_done(tmp_path: Path):
    """cp4 / FR-009 / TM-007: missing verdict in qa yaml must NOT be treated as pass / cannot route to DONE."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-001.yaml"
    qa_file.write_text("epic_id: T-HUB-040\nsummary: no verdict field here\n", encoding="utf-8")

    save_epic_state(tmp_path, {"armed_epic": "T-HUB-040", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="qa complete with missing verdict",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    # Missing verdict should either fail validation or not route to DONE
    if res.ok:
        written = read_active_context(tmp_path)
        assert "mode: DONE" not in written
        assert "EPIC_DONE" not in written
    else:
        assert not res.ok


def test_finish_qa_reviewer_lock_on_re_qa(tmp_path: Path):
    """cp4 / FR-012 / TM-006: re-QA pass path requires reviewer evidence matching current run."""
    mb_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-HUB-040"
    mb_dir.mkdir(parents=True, exist_ok=True)
    qa_file = mb_dir / "qa-20260905-new.yaml"
    qa_file.write_text("verdict: pass\nepic_id: T-HUB-040\n", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040",
            "armed_role": "BACK",
            "phase_run_id": "session-run-2",
            "qa_after_bugfix": {
                "epic_id": "T-HUB-040",
                "phase_run_id": "session-run-1",
                "existing_artifacts": ["memory-bank/back/qa/T-HUB-040/qa-20260905-fail.yaml"],
            },
            # No reviewer evidence or stale evidence
            "last_reviewer_verdict": None,
        },
    )

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="re-qa pass without reviewer",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_reviewer_required" in res.diagnostic_codes


def test_060_shaped_fixture_bugfix_prose_not_sot(tmp_path: Path):
    """cp2 / FR-011: T-HUB-060-shaped fixture: fail yaml + bugfix prose «1942 passed» is not SoT."""
    epic = "T-HUB-060"
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / epic
    qa_dir.mkdir(parents=True, exist_ok=True)
    qa_file = qa_dir / "qa-20260905-fail.yaml"
    qa_file.write_text("verdict: fail\nepic_id: T-HUB-060\nissues:\n  - some blocker\n", encoding="utf-8")

    bugfix_dir = tmp_path / "memory-bank" / "back" / "bugfix" / epic
    bugfix_dir.mkdir(parents=True, exist_ok=True)
    bugfix_file = bugfix_dir / "bugfix-20260905.md"
    bugfix_file.write_text("# Bugfix\n\nAll tests fixed: 1942 passed, 0 failed in test suite.\n", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_role": "BACK",
            "phase_run_id": "session-2",
            "qa_after_bugfix": {
                "epic_id": epic,
                "phase_run_id": "session-1",
                "existing_artifacts": [f"memory-bank/back/qa/{epic}/qa-20260905-fail.yaml"],
            },
        },
    )

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="s05",
        done_summary="re-qa trying to finish with prose claiming 1942 passed",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok is False
    assert "qa_new_artifact_required" in res.diagnostic_codes
