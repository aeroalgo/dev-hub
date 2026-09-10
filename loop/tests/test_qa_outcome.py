"""Tests for loop-qa-outcome/v1 classifier."""

from __future__ import annotations

from loop.qa_outcome import (
    classify_qa_outcome,
    resolve_qa_suite_plan,
    suite_plan_after_changes,
)
from loop.schemas.qa_outcome import SCHEMA_LOOP_QA_OUTCOME


def test_classify_suite_red_to_bugfix() -> None:
    out = classify_qa_outcome({"suite_ok": False})
    assert out.schema_version == SCHEMA_LOOP_QA_OUTCOME
    assert out.kind == "suite_red"
    assert out.next_action == "bugfix"


def test_classify_plan_mismatch_and_ac_gap() -> None:
    assert classify_qa_outcome({"suite_ok": True, "plan_mismatch": True}).next_action == "bugfix"
    assert classify_qa_outcome({"suite_ok": True, "ac_gap": True}).next_action == "bugfix"


def test_classify_transport_retry_then_need_human() -> None:
    assert classify_qa_outcome({"transport_broken": True}).next_action == "retry_spawn"
    assert classify_qa_outcome({"transport_broken": True, "transport_retries": 1}).next_action == "need_human"


def test_classify_green_verify_paths() -> None:
    assert classify_qa_outcome({"suite_ok": True}).next_action == "verify_qa"
    assert classify_qa_outcome({"suite_ok": True, "verify_verdict": "PASS"}).next_action == "done"
    assert classify_qa_outcome({"suite_ok": True, "verify_verdict": "FAIL"}).next_action == "bugfix"
    assert classify_qa_outcome({"suite_ok": True, "verify_verdict": "BLOCKED"}).next_action == "bugfix"


def test_suite_plan_runtime_vs_targeted() -> None:
    full = suite_plan_after_changes(["loop/x.py"])
    assert full.suite_scope == "full"
    targeted = suite_plan_after_changes(["apps/tests/test_x.py"])
    assert targeted.suite_scope == "targeted"
    assert "apps/tests/test_x.py" in targeted.suite_command
    unknown = suite_plan_after_changes([])
    assert unknown.suite_scope == "full"


def test_resolve_qa_suite_plan_after_bugfix() -> None:
    plan = resolve_qa_suite_plan(
        ".",
        {
            "armed_epic": "T-DEMO",
            "qa_after_bugfix": {
                "epic_id": "T-DEMO",
                "phase_run_id": "s1",
                "existing_artifacts": [],
                "suite_scope": "targeted",
                "suite_command": "bin/pytest apps/tests/test_x.py -q --tb=line",
                "changed_paths": ["apps/tests/test_x.py"],
            },
        },
    )
    assert plan.suite_scope == "targeted"
    assert plan.suite_command.endswith("--tb=line")
