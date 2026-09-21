from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.cli import _gate_protocol, _phase_gate_agent
from loop.kernel.analyze import analyze_required_before_implement, index_content_fingerprint
from loop.kernel.index import Step, implement_path
from loop.kernel.lifecycle import SubagentLifecycle
from loop.kernel.model import CursorStatus, RuntimeResult
from loop.kernel.runtime import CodexRuntime, Runtime
from loop.kernel.session import SessionOutcome, SessionSupervisor
from loop.kernel.store import CursorStore, LoopPaths
from loop.kernel.verdict import BoundaryIdentity, GateVerdict, SCHEMA_GATE_VERDICT, SCHEMA_REPAIR_RESULT, validate_boundary, validate_message
from loop.config import LoopSettings


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_project(root: Path) -> LoopPaths:
    write(root / "memory-bank/back/plan/E1/yaml/decompose-index.yaml", """
schema: epic-decompose-index/v1
epic_id: E1
steps:
  - id: s01
    file: s01-one.yaml
    status: pending
  - id: s02
    file: s02-two.yaml
    status: pending
""")
    write(root / "memory-bank/back/plan/E1/yaml/s01-one.yaml", "step_id: s01\n")
    write(root / "memory-bank/back/plan/E1/yaml/s02-two.yaml", "step_id: s02\n")
    write(
        root / "memory-bank/back/analyze/E1/analyze-20260921-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n",
    )
    return LoopPaths(project=root, hub=root / "hub")


def _finish_via_gate(engine: LoopEngine):
    cursor = engine.store.read()
    assert cursor is not None
    agent = {
        "DECOMPOSE": "verify-decompose",
        "ANALYZE": "analyze-verify",
        "IMPLEMENT": "verify-implement",
        "TASK": "verify-implement",
        "REFACTOR": "verify-implement",
        "BUGFIX": "verify-bugfix",
        "QA": "verify-qa",
    }.get(cursor.phase)
    assert agent is not None
    return engine.accept_verdict(
        GateVerdict(
            schema=SCHEMA_GATE_VERDICT,
            agent_id=agent,
            verdict="PASS",
            step_id=cursor.step_id,
            session_id=cursor.session_id,
            epic_id=cursor.epic_id,
            recorded_at="2026-09-18T19:00:00+00:00",
        ),
        expected_agent_id=agent,
    )


def test_cursor_is_the_only_runtime_state_and_finish_advances_index(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)

    cursor = engine.start("E1")
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"
    assert paths.cursor.is_file()
    assert not (paths.runtime / "state.json").exists()
    assert not (paths.runtime / "checkpoint.json").exists()
    assert not (paths.runtime / "last-session.json").exists()

    transition = _finish_via_gate(engine)
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text()
    assert "id: s01" in index and "status: completed" in index


def test_new_plan_starts_decompose_before_index_exists(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")

    cursor = LoopEngine(paths).start("E2")

    assert cursor.phase == "DECOMPOSE"
    assert cursor.step_id == "DECOMPOSE"
    assert cursor.status == CursorStatus.ACTIVE
    context = paths.active_context.read_text(encoding="utf-8")
    assert "memory-bank/back/plan/E2/md/plan.md" in context


def test_rewind_forces_analyze_even_after_implementation_progress(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)

    transition = engine.rewind("ANALYZE")

    assert transition.phase == "ANALYZE"
    assert transition.step_id == "ANALYZE"
    assert engine.store.read().status == CursorStatus.ACTIVE
    after_analyze = _finish_via_gate(engine)
    assert after_analyze.phase == "IMPLEMENT"
    assert after_analyze.step_id == "s02"


def test_decompose_finish_requires_index_and_hands_off_to_analyze(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    engine.start("E2")
    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E2
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )

    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/steps/s01.yaml",
        """
schema: epic-decompose/v1
role: back
step_id: s01
plan_id: E2
title: s01
next_phase: BACK IMPLEMENT
goal: outcome
plan_contract: {}
context: {}
as_built: []
delta: []
deletes: []
out_of_scope: []
skills: {}
checkpoints: []
verify: []
tdd: []
""",
    )

    transition = _finish_via_gate(engine)

    assert transition.phase == "ANALYZE"
    assert transition.step_id == "ANALYZE"
    assert engine.store.read().phase == "ANALYZE"


def test_decompose_finish_rejects_incomplete_tree(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E2/md/plan.md", "# Plan: E2\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)
    engine.start("E2")
    write(
        tmp_path / "memory-bank/back/plan/E2/yaml/decompose-index.yaml",
        """
schema: epic-decompose-index/v1
plan_id: E2
steps:
  - id: s01
    file: s01.yaml
    title: s01
    next_phase: BACK IMPLEMENT
    status: pending
""",
    )

    with pytest.raises(FileNotFoundError, match="decompose shard missing"):
        _finish_via_gate(engine)

    assert engine.store.read().phase == "DECOMPOSE"


def test_loop_holds_at_analyze_until_zero_critical_artifact_exists(tmp_path: Path) -> None:
    write(tmp_path / "memory-bank/back/plan/E3/md/plan.md", "# Plan: E3\n")
    write(
        tmp_path / "memory-bank/back/plan/E3/yaml/decompose-index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: E3\nsteps:\n"
        "- id: s01\n  file: s01.yaml\n  status: pending\n",
    )
    write(tmp_path / "memory-bank/back/plan/E3/yaml/s01.yaml", "step_id: s01\n")
    paths = LoopPaths(project=tmp_path, hub=tmp_path / "hub")
    engine = LoopEngine(paths)

    assert engine.start("E3").phase == "ANALYZE"
    write(
        tmp_path / "memory-bank/back/analyze/E3/analyze-20260921-fail.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 1\n",
    )
    with pytest.raises(TransitionError, match="critical_findings"):
        _finish_via_gate(engine)

    write(
        tmp_path / "memory-bank/back/analyze/E3/analyze-20260922-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n",
    )
    transition = _finish_via_gate(engine)
    assert transition.phase == "IMPLEMENT"
    assert transition.step_id == "s01"


def test_analyze_gate_rejects_stale_index_and_unknown_step_refs(tmp_path: Path) -> None:
    index = tmp_path / "memory-bank/back/plan/E4/yaml/decompose-index.yaml"
    write(index, "schema: epic-decompose-index/v1\nplan_id: E4\nsteps:\n- id: s01\n  status: pending\n")
    fingerprint = index_content_fingerprint(index)
    write(
        tmp_path / "memory-bank/back/analyze/E4/analyze-20260921-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\n"
        f"index_fingerprint: {fingerprint}\nmetrics:\n  critical_count: 0\n"
        "findings:\n- id: A1\n  step_ref: s99\n",
    )

    result = analyze_required_before_implement(
        tmp_path,
        "back",
        "E4",
        [{"id": "s01", "status": "pending"}],
        index_path_override=index,
    )
    assert result["required"] is True
    assert result["reason"] == "analyze_stale"


def test_implement_artifact_path_has_no_duplicate_epic_prefix(tmp_path: Path) -> None:
    step = Step("s01", "pending", "wire", "s01-wire.yaml")

    assert implement_path(tmp_path, "back", "E5-mode-a", step) == (
        tmp_path / "memory-bank/back/implement/E5-mode-a/s01-wire.yaml"
    )


def test_lifecycle_has_one_transition_path(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)
    assert engine.store.read().phase == "AUDIT"

    write(
        tmp_path / "memory-bank/back/audit/E1/audit.yaml",
        """schema: epic-audit/v2
epic_id: E1
plan_id: E1
converged: true
findings: []
check_matrix:
  - source_ref: plan:E1
    status: pass
    evidence: implementation evidence
    verify: targeted check
""",
    )
    engine.finish(step_id="AUDIT")
    assert engine.store.read().phase == "QA"

    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    with pytest.raises(TransitionError, match="bugfix_queue_missing"):
        _finish_via_gate(engine)
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
epic_id: E1
items:
  - id: BF-001
    status: open
""",
    )
    _finish_via_gate(engine)
    assert engine.store.read().phase == "BUGFIX"

    write(tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md", "# root cause and fix\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        """schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pass
  command: bin/pytest -q
  last_run_at: 2026-09-21T00:00:00Z
  evidence: 1 passed
items:
  - id: BF-001
    status: done
""",
    )
    _finish_via_gate(engine)
    assert engine.store.read().phase == "QA"

    with pytest.raises(TransitionError, match="qa_new_artifact_required"):
        _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-pass.yaml", "schema: epic-qa/v1\nverdict: pass\n")
    _finish_via_gate(engine)
    assert engine.store.read().status == CursorStatus.COMPLETE


def test_phase_gate_agents_cover_all_machine_checked_modes() -> None:
    assert _phase_gate_agent("DECOMPOSE") == "verify-decompose"
    assert _phase_gate_agent("ANALYZE") == "analyze-verify"
    assert _phase_gate_agent("BUGFIX") == "verify-bugfix"
    assert _phase_gate_agent("QA") == "verify-qa"
    assert _phase_gate_agent("AUDIT") is None


def test_gate_prompt_contains_exact_identity_contract_and_repair_loop(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    prompt = _gate_protocol(cursor, tmp_path, "verify-implement")

    assert f"GATE_IDENTITY session_id={cursor.session_id} epic_id=E1 step_id=s01" in prompt
    assert "ALLOW READ:" in prompt
    assert "gate-repair" in prompt
    assert "loop-repair-result/v1" in prompt
    assert "verdict session mismatch" in prompt
    assert "T-004-mode-a-live-ready-analyze-verify" not in prompt
    engine.rewind("ANALYZE")
    analyze_cursor = engine.store.read()
    assert analyze_cursor is not None
    analyze_prompt = _gate_protocol(analyze_cursor, tmp_path, "analyze-verify")
    assert "FINDINGS:" in analyze_prompt
    assert "COVERAGE:" in analyze_prompt
    assert "ALLOW READ:" in analyze_prompt
    assert f"GATE_IDENTITY session_id={analyze_cursor.session_id} epic_id=E1 step_id=ANALYZE" in analyze_prompt


def test_gate_repair_result_is_validated_and_recorded(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": "evidence-1",
        "status": "done",
        "fixed_blockers": ["B1"],
        "remaining_blockers": [],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    message = chr(96) * 3 + "json\n" + json.dumps(payload) + "\n" + chr(96) * 3

    action = lifecycle.stop(
        {
            "cwd": str(tmp_path),
            "agent_type": "gate-repair",
            "last_assistant_message": message,
        }
    )

    assert action.ok
    assert action.transition["metadata"]["repair_status"] == "done"
    assert '"event": "repair_recorded"' in paths.events.read_text(encoding="utf-8")
    assert engine.store.read().session_id == cursor.session_id


def test_finish_requires_verify_pass_and_fail_requires_repair(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")

    with pytest.raises(TransitionError, match="verify-implement PASS"):
        engine.finish(step_id="s01")

    failed = GateVerdict(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-implement",
        verdict="FAIL",
        step_id=cursor.step_id,
        session_id=cursor.session_id,
        epic_id=cursor.epic_id,
        recorded_at="2026-09-18T19:00:00+00:00",
    )
    engine.accept_verdict(failed, expected_agent_id="verify-implement")
    with pytest.raises(TransitionError, match="repair and re-verify"):
        engine.finish(step_id="s01")


def test_audit_and_bugfix_phase_contracts_fail_closed(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)

    write(
        tmp_path / "memory-bank/back/audit/E1/audit.yaml",
        """schema: epic-audit/v2
epic_id: E1
converged: false
findings: []
check_matrix:
  - source_ref: plan:E1
    status: fail
    evidence: missing behavior
    verify: targeted check
""",
    )
    with pytest.raises(TransitionError, match="converged audit artifact"):
        engine.finish(step_id="AUDIT")

    write(
        tmp_path / "memory-bank/back/audit/E1/audit.yaml",
        """schema: epic-audit/v2
epic_id: E1
converged: true
findings: []
check_matrix:
  - source_ref: plan:E1
    status: pass
    evidence: implementation evidence
    verify: targeted check
""",
    )
    engine.finish(step_id="AUDIT")
    write(tmp_path / "memory-bank/back/qa/E1/qa-20260921-fail.yaml", "schema: epic-qa/v1\nverdict: fail\n")
    write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        "schema: epic-bugfix-queue/v1\nitems:\n  - id: BF-1\n    status: open\n",
    )
    _finish_via_gate(engine)
    write(tmp_path / "memory-bank/back/bugfix/E1/bugfix-20260921-fix.md", "# fix\n")
    with pytest.raises(TransitionError, match="bugfix_queue_open"):
        _finish_via_gate(engine)


def test_retry_is_bounded_by_one_counter(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    first = engine.retry("runtime_exit_1")
    second = engine.retry("runtime_exit_2")
    assert first.attempt == 1
    assert second.attempt == 2
    payload = json.loads(paths.cursor.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema",
        "revision",
        "epic_id",
        "role",
        "phase",
        "step_id",
        "phase_epoch",
        "status",
        "attempt",
        "session_id",
        "failure",
        "updated_at",
    }


def test_session_supervisor_commits_failure_and_halt_atomically(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")

    class FailingRuntime:
        def run(self, prompt, *, model, project, log_path, timeout):
            return RuntimeResult("test", 17, log_path, message="runtime failed")

    run = SessionSupervisor(engine, FailingRuntime(), timeout=1, max_attempts=1, backoff=0).run_step(
        "work", model="test", project=tmp_path, session_id="session-1"
    )

    assert run.outcome == SessionOutcome.RUNTIME_FAILURE
    assert run.transition is not None
    cursor = engine.store.read()
    assert cursor is not None
    assert cursor.status == CursorStatus.HALTED
    assert cursor.failure is not None
    assert cursor.failure.category == "session"
    assert cursor.failure.code == "retry_exhausted"
    assert cursor.failure.details["exit_code"] == 17


def test_phase_finish_requires_evidence_and_halt_is_terminal(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    _finish_via_gate(engine)
    _finish_via_gate(engine)

    with pytest.raises(TransitionError, match="audit artifact"):
        engine.finish(step_id="AUDIT")

    halted = engine.halt("manual stop")
    assert halted.status == CursorStatus.HALTED
    with pytest.raises(TransitionError, match="halted"):
        engine.finish(step_id="AUDIT")


def test_cursor_transaction_recovers_after_projection_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    original = CursorStore._write_cursor_unlocked
    failed = False

    def fail_once(store: CursorStore, cursor) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated cursor projection failure")
        original(store, cursor)

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_once)
    with pytest.raises(OSError, match="simulated cursor"):
        engine.start("E1")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.epic_id == "E1"
    assert recovered.step_id == "s01"
    records = paths.events.read_text(encoding="utf-8").splitlines()
    assert sum('"record_type": "commit"' in line for line in records) == 1
    assert engine.store.read().revision == recovered.revision


def test_journal_recovers_an_incomplete_trailing_record(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    with paths.events.open("ab") as handle:
        handle.write(b'{"schema":"loop-journal/v1"')

    recovered = engine.store.read()
    assert recovered is not None
    engine.record_event({"event": "after_partial_journal"})
    records = [json.loads(line) for line in paths.events.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "after_partial_journal"


def test_legacy_cursor_schema_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-cursor/v1", "epic_id": "E1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported cursor schema"):
        LoopEngine(paths).status()


def test_legacy_cursor_failure_field_is_not_used_as_runtime_state(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    paths.runtime.mkdir(parents=True, exist_ok=True)
    paths.cursor.write_text(json.dumps({"schema": "loop-state/v2", "last_error": "old failure"}), encoding="utf-8")

    with pytest.raises(ValueError, match="legacy cursor field last_error"):
        LoopEngine(paths).status()


def test_finish_recovers_index_and_context_from_prepared_transaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    original = CursorStore._write_cursor_unlocked

    def fail_projection(_store: CursorStore, _cursor) -> None:
        raise OSError("simulated finish projection failure")

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", fail_projection)
    with pytest.raises(OSError, match="simulated finish"):
        _finish_via_gate(engine)

    monkeypatch.setattr(CursorStore, "_write_cursor_unlocked", original)
    recovered = engine.store.read()
    assert recovered is not None
    assert recovered.step_id == "s02"
    index = (tmp_path / "memory-bank/back/plan/E1/yaml/decompose-index.yaml").read_text(encoding="utf-8")
    assert "status: completed" in index
    assert "step_id: s02" in paths.active_context.read_text(encoding="utf-8")


def _verdict_message(cursor, *, agent_id: str = "verify-implement", verdict: str = "PASS") -> str:
    payload = {
        "schema": SCHEMA_GATE_VERDICT,
        "agent_id": agent_id,
        "verdict": verdict,
        "step_id": cursor.step_id,
        "session_id": cursor.session_id,
        "epic_id": cursor.epic_id,
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    return "```json\n" + json.dumps(payload) + "\n```"


def test_gate_verdict_is_strict_and_identity_bound(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    identity = BoundaryIdentity(cursor.session_id, cursor.epic_id, cursor.step_id, "verify-implement")

    valid = validate_message(_verdict_message(cursor), identity=identity)
    assert valid.valid and valid.record is not None
    assert valid.record.agent_id == "verify-implement"

    wrong_step = _verdict_message(cursor).replace('"step_id": "s01"', '"step_id": "s02"')
    rejected = validate_message(wrong_step, identity=identity)
    assert not rejected.valid
    assert "verdict_wrong_step_id" in rejected.diagnostic_codes

    extra = json.loads(_verdict_message(cursor).split("\n", 2)[1])
    extra["reason"] = "human text is not part of the wire contract"
    rejected_extra = validate_boundary(SCHEMA_GATE_VERDICT, extra, identity=identity)
    assert not rejected_extra.valid
    assert any(code.startswith("schema_") for code in rejected_extra.diagnostic_codes)


def test_subagent_pass_finishes_once_and_duplicate_is_idempotent(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor),
    }

    accepted = lifecycle.stop(payload)
    assert accepted.ok
    assert accepted.transition["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"

    duplicate = lifecycle.stop(payload)
    assert duplicate.ok
    assert duplicate.transition["event"] == "verdict_duplicate"
    assert engine.store.read().step_id == "s02"


def test_subagent_fail_or_blocked_is_recorded_without_finishing(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    lifecycle = SubagentLifecycle(paths)

    for verdict in ("FAIL", "BLOCKED"):
        action = lifecycle.stop(
            {
                "cwd": str(tmp_path),
                "agent_type": "verify-implement",
                "last_assistant_message": _verdict_message(cursor, verdict=verdict),
            }
        )
        assert action.ok
        assert action.transition["event"] == "verdict_recorded"
        assert action.transition["reason"] == verdict
        assert engine.store.read().step_id == "s01"

    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_recorded"') == 2


def test_subagent_invalid_verdict_has_atomic_retry_budget(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    engine.start("E1")
    lifecycle = SubagentLifecycle(paths)
    payload = {"cwd": str(tmp_path), "agent_type": "verify-implement", "last_assistant_message": "no json"}

    first = lifecycle.stop(payload)
    second = lifecycle.stop(payload)
    third = lifecycle.stop(payload)
    assert first.exit_code == second.exit_code == third.exit_code == 2
    assert "retry 1/2" in first.reason
    assert "retry 2/2" in second.reason
    assert third.reason == "schema_retry_exhausted:verify-implement"
    assert engine.store.read().status == CursorStatus.HALTED
    events = paths.events.read_text(encoding="utf-8")
    assert events.count('"event": "verdict_rejected"') == 3
    assert '"event": "halt"' in events


def test_subagent_stop_hook_accepts_pydantic_verdict(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "last_assistant_message": _verdict_message(cursor),
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-stop.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    assert hook_payload["ok"] is True
    assert hook_payload["transition"]["reason"] == "subagent-stop:verify-implement:PASS"
    assert engine.store.read().step_id == "s02"


def test_subagent_start_hook_injects_cursor_identity(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    environment = os.environ.copy()
    environment.update(
        {
            "LOOP_ACTIVE": "1",
            "EPIC_LOOP": "1",
            "LOOP_WORKFLOW_HOOKS": "loop",
            "PROJECT_ROOT": str(tmp_path),
            "DEV_HUB": str(paths.hub),
        }
    )
    payload = {
        "cwd": str(tmp_path),
        "agent_type": "verify-implement",
        "prompt": "check the implementation and return the gate verdict",
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "harness/hooks/subagent-start.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    hook_payload = json.loads(result.stdout)
    context = hook_payload["hookSpecificOutput"]["additionalContext"]
    assert f"GATE_IDENTITY session_id={cursor.session_id} epic_id=E1 step_id=s01" in context
    assert "validate-verdict" in context


def test_native_validator_command_validates_gate_payload(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    message = _verdict_message(cursor)
    payload = json.loads(message.split("\n", 2)[1])
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True


def test_native_validator_accepts_repair_result_schema(tmp_path: Path) -> None:
    seed_project(tmp_path)
    payload = {
        "schema": SCHEMA_REPAIR_RESULT,
        "agent_id": "gate-repair",
        "parent_evidence_id": "evidence-1",
        "status": "partial",
        "fixed_blockers": ["scope"],
        "remaining_blockers": ["tests"],
        "recorded_at": "2026-09-18T19:00:00+00:00",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate",
            "--project",
            str(tmp_path),
            "--schema",
            SCHEMA_REPAIR_RESULT,
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    result_verdict_command = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[2] / "bin/loop.py"),
            "validate-verdict",
            "--project",
            str(tmp_path),
            "--payload",
            json.dumps(payload),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result_verdict_command.returncode == 0, result_verdict_command.stderr
    assert json.loads(result_verdict_command.stdout)["valid"] is True


def test_codex_uses_omniroute_wrapper_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper = tmp_path / "codex" / "bin" / "codex-omniroute.sh"
    write(wrapper, "#!/usr/bin/env bash\n")
    wrapper.chmod(0o755)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "1")
    monkeypatch.setenv("DEV_HUB", str(tmp_path))

    assert CodexRuntime().executable() == str(wrapper)


def test_codex_can_explicitly_disable_omniroute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setenv("CODEX_USE_OMNIROUTE", "0")
    assert CodexRuntime().executable() == shutil.which("codex")


def test_codex_command_is_headless_and_bypasses_nested_sandbox(tmp_path: Path) -> None:
    command = CodexRuntime().command("do work", model="model", project=tmp_path)

    assert command[1:5] == [
        "exec",
        "--json",
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    assert "--dangerously-bypass-hook-trust" in command
    assert command[command.index("--enable") + 1] == "multi_agent"
    assert command[-1] == "do work"


def test_codex_renders_compact_progress_events() -> None:
    runtime = CodexRuntime()
    started = runtime._progress_line(
        json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "rg -n foo src"}})
    )
    completed = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "apply_patch < patch", "status": "completed", "exit_code": 0},
            }
        )
    )

    assert started == "  • read  rg -n foo src"
    assert completed == "  ✓ write finished (exit=0)"


def test_codex_labels_gate_spawn_from_current_phase_when_payload_omits_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = seed_project(tmp_path)
    monkeypatch.setenv("DEV_HUB", str(paths.hub))
    engine = LoopEngine(paths)
    engine.start("E1")
    runtime = CodexRuntime()
    runtime._progress_started(tmp_path, "")

    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "spawn_agent",
                    "prompt": "GATE_IDENTITY session_id=session-1 epic_id=E1 step_id=s01",
                    "receiver_thread_ids": ["thread-1"],
                },
            }
        )
    )

    assert rendered is not None
    assert "subagent spawn type=verify-implement" in rendered


def test_codex_progress_reports_errors_without_raw_json() -> None:
    runtime = CodexRuntime()
    rendered = runtime._progress_line(json.dumps({"type": "error", "message": "metadata fallback"}))

    assert rendered == "  ! metadata fallback"
    assert "{\"type\"" not in rendered


def test_codex_renders_subagent_state_and_json_verdict() -> None:
    runtime = CodexRuntime()
    verdict = (
        "```json\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement",'
        '"verdict":"PASS"}\n'
        "```"
    )
    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-1": {"status": "completed", "message": verdict}
                    },
                },
            }
        )
    )

    assert "subagent verify-implement id=thread-1 status=completed" in rendered
    assert "loop-gate-verdict/v1" in rendered
    assert '"verdict":"PASS"' in rendered


def test_codex_subagent_pass_is_applied_to_new_kernel(tmp_path: Path) -> None:
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)
    cursor = engine.start("E1")
    runtime = CodexRuntime()
    runtime._progress_started(tmp_path, "")
    runtime._collab_lifecycle = SubagentLifecycle(paths)
    message = _verdict_message(cursor)

    rendered = runtime._progress_line(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-1": {"status": "completed", "message": message}
                    },
                },
            }
        )
    )

    assert "verdict verify-implement=PASS -> IMPLEMENT/s02" in rendered
    assert engine.store.read().step_id == "s02"


def test_runtime_captures_child_output_without_polluting_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    class TestRuntime(Runtime):
        name = "test"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            script = (
                "from pathlib import Path\n"
                "import time\n"
                "print('runtime-start', flush=True)\n"
                "while not Path('release').exists(): time.sleep(0.01)\n"
                "print('runtime-end', flush=True)\n"
            )
            return [sys.executable, "-u", "-c", script]

    result: list[object] = []
    thread = threading.Thread(
        target=lambda: result.append(
            TestRuntime().run(
                "prompt",
                model="model",
                project=tmp_path,
                log_path=tmp_path / "session.log",
                timeout=5,
            )
        ),
        daemon=True,
    )
    thread.start()
    (tmp_path / "release").write_text("release\n", encoding="utf-8")
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert result and result[0].exit_code == 0
    assert capsys.readouterr().out == ""
    log = (tmp_path / "session.log").read_text(encoding="utf-8")
    assert "runtime-start" in log
    assert "runtime-end" in log


def test_runtime_heartbeat_elapsed_and_idle_timeout_are_recorded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    class SilentRuntime(Runtime):
        name = "silent"

        def executable(self) -> str:
            return sys.executable

        def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
            return [sys.executable, "-u", "-c", "import time; time.sleep(3)"]

    result = SilentRuntime(
        LoopSettings(
            status_heartbeat=1,
            stream_idle_timeout=1,
            session_kill_grace=1,
            collaboration_wait_timeout=1,
        )
    ).run(
        "prompt",
        model="model",
        project=tmp_path,
        log_path=tmp_path / "session-silent.log",
        timeout=3,
    )

    assert result.exit_code == 124
    assert result.idle_timed_out is True
    assert result.timed_out is False
    assert result.hung is True
    assert result.elapsed_sec >= 1
    assert result.heartbeat_count >= 1
    captured = capsys.readouterr().out
    assert "heartbeat:" in captured
    assert "idle timeout:" in captured
    log = (tmp_path / "session-silent.log").read_text(encoding="utf-8")
    assert "SESSION_HEARTBEAT" in log
    assert "SESSION_IDLE_TIMEOUT" in log
    assert "SESSION_END" in log
