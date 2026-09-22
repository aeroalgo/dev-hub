from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from .boundary import BoundaryService
from .analyze import analyze_required_before_implement
from .index import (
    Queue,
    audit_is_converged,
    bugfix_queue_path,
    bugfix_queue_intake,
    bugfix_report_paths,
    bugfix_queue_state,
    implement_path,
    index_path,
    load_queue,
    phase_artifacts,
    prepare_step_status,
    qa_verdict,
    validate_decompose_tree,
)
from .model import Cursor, CursorStatus, FailureRecord, Transition
from .store import CommitResult, LoopPaths, StoreTransaction, TransactionPlan, CursorStore, file_digest
from .verdict import GateVerdict, MANAGED_GATE_AGENTS


class TransitionError(RuntimeError):
    pass


_PHASE_GATE_AGENTS = {
    "DECOMPOSE": "verify-decompose",
    "ANALYZE": "analyze-verify",
    "IMPLEMENT": "verify-implement",
    "TASK": "verify-implement",
    "REFACTOR": "verify-implement",
    "BUGFIX": "verify-bugfix",
    "QA": "verify-qa",
}


class LoopEngine:
    """The domain facade; CursorStore owns every state mutation."""

    def __init__(self, paths: LoopPaths):
        self.paths = paths
        self.store = CursorStore(paths)
        self.boundary = BoundaryService(paths)

    def _queue(self, cursor: Cursor) -> Queue:
        return load_queue(self.paths.project, cursor.role, cursor.epic_id)

    def _analyze_gate(self, queue: Queue, *, force: bool = False) -> dict[str, Any]:
        return analyze_required_before_implement(
            self.paths.project,
            queue.role,
            queue.epic_id,
            ({"id": step.step_id, "status": step.status} for step in queue.steps),
            index_path_override=queue.path,
            force=force,
        )

    def _plan_path(self, cursor: Cursor) -> Path:
        return index_path(self.paths.project, cursor.role, cursor.epic_id).parent.parent / "md" / "plan.md"

    def _phase_after_queue(self, queue: Queue) -> tuple[str, str]:
        audit = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "audit")
        qa = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
        bugfix_queue = bugfix_queue_path(self.paths.project, queue.role, queue.epic_id)
        if not audit:
            return "AUDIT", "audit artifact required"
        audit_ready, audit_reason = audit_is_converged(self.paths.project, queue.role, queue.epic_id)
        if not audit_ready:
            return "AUDIT", audit_reason
        if not qa:
            return "QA", "qa artifact required"
        verdict = qa_verdict(qa[-1])
        if verdict in {"fail", "failed", "blocked"}:
            queue_ready, _ = bugfix_queue_state(self.paths.project, queue.role, queue.epic_id)
            if bugfix_queue.is_file() and queue_ready:
                return "QA", "bugfix exists; re-qa required"
            return "BUGFIX", "qa failed"
        if verdict in {"pass", "passed", "complete", "completed"}:
            return "DONE", "qa passed"
        return "QA", "qa verdict missing"

    def _target(self, cursor: Cursor, queue: Queue | None = None) -> tuple[str, str, str]:
        if queue is None:
            canonical_index = index_path(self.paths.project, cursor.role, cursor.epic_id)
            if not canonical_index.is_file():
                plan = self._plan_path(cursor)
                if not plan.is_file():
                    raise FileNotFoundError(f"canonical plan missing: {plan}")
                return "DECOMPOSE", "DECOMPOSE", f"canonical decompose index pending: {canonical_index}"
            active_queue = self._queue(cursor)
        else:
            active_queue = queue
        if active_queue.pending:
            gate = self._analyze_gate(active_queue)
            if gate["required"]:
                return "ANALYZE", "ANALYZE", f"ANALYZE gate: {gate['reason']}"
            step = active_queue.pending[0]
            return "IMPLEMENT", step.step_id, f"pending step {step.step_id}"
        phase, reason = self._phase_after_queue(active_queue)
        return phase, phase, reason

    @staticmethod
    def _copy_cursor(cursor: Cursor) -> Cursor:
        return Cursor.from_dict(cursor.to_dict())

    @staticmethod
    def _queue_after_step(queue: Queue, step_id: str) -> Queue:
        return replace(
            queue,
            steps=tuple(
                replace(step, status="completed") if step.step_id == step_id else step
                for step in queue.steps
            ),
        )

    def _render_body(self, cursor: Cursor, queue: Queue | None = None) -> str:
        if cursor.phase == "BUGFIX":
            load_path = bugfix_queue_path(self.paths.project, cursor.role, cursor.epic_id)
        else:
            load_path = queue.path if queue is not None else self._plan_path(cursor)
        lines = [
            "---",
            "schema: loop-generated-context/v1",
            f"role: {cursor.role.upper()}",
            f"mode: {cursor.phase}",
            f"epic_id: {cursor.epic_id}",
            f"step_id: {cursor.step_id}",
            f"phase_epoch: {cursor.phase_epoch}",
            f"state_revision: {cursor.revision + 1}",
            "generated: true",
            "---",
            "",
            "## load_now",
            f"1. {load_path.relative_to(self.paths.project).as_posix()} — {'queue/status' if queue is not None else 'source plan'}",
        ]
        phase_directories = {
            "ANALYZE": "analyze",
            "AUDIT": "audit",
            "QA": "qa",
            "BUGFIX": "bugfix",
        }
        artifact_kind = phase_directories.get(cursor.phase)
        next_load_number = 2
        if artifact_kind:
            lines.append(
                f"{next_load_number}. memory-bank/{cursor.role}/{artifact_kind}/{cursor.epic_id}/ — current phase artifacts"
            )
            next_load_number += 1
        if queue is not None and cursor.step_id and cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}:
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step and step.shard:
                lines.append(f"{next_load_number}. {step.shard} — current step artifact")
                next_load_number += 1
            if step:
                lines.append(
                    f"{next_load_number}. {implement_path(self.paths.project, queue.role, queue.epic_id, step).relative_to(self.paths.project).as_posix()} — implement artifact"
                )
        lines.extend(
            [
                "",
                f"## Handoff {cursor.phase}",
                f"- Current cursor: `{cursor.epic_id}/{cursor.phase}/{cursor.step_id}`.",
                "- This file is generated by loop/kernel; do not edit it as state.",
                f"- Finish with: `python3 $DEV_HUB/bin/loop.py finish --project {self.paths.project} --step {cursor.step_id}`.",
                "",
                self.boundary.context(cursor),
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _failure(category: str, code: str, message: str, *, retryable: bool, attempt: int, details: dict[str, Any] | None = None) -> FailureRecord:
        return FailureRecord(category, code, message, retryable, attempt, details=details or {})

    @staticmethod
    def _required_gate_agent(phase: str) -> str | None:
        return _PHASE_GATE_AGENTS.get(str(phase or "").upper())

    def _qa_failure_ready(self, cursor: Cursor) -> bool:
        artifacts = phase_artifacts(self.paths.project, cursor.role, cursor.epic_id, "qa")
        qa_status = qa_verdict(artifacts[-1]) if artifacts else None
        queue_intake, _ = bugfix_queue_intake(self.paths.project, cursor.role, cursor.epic_id)
        queue_ready, queue_reason = bugfix_queue_state(self.paths.project, cursor.role, cursor.epic_id)
        return (
            cursor.phase == "QA"
            and qa_status in {"fail", "failed", "blocked"}
            and queue_intake
            and not queue_ready
            and queue_reason == "bugfix_queue_open"
        )

    @staticmethod
    def _pending_qa_failure(transaction: StoreTransaction, cursor: Cursor) -> dict[str, Any] | None:
        event = transaction.latest_event("verdict_recorded")
        if event is None:
            return None
        expected = {
            "session_id": cursor.session_id,
            "epic_id": cursor.epic_id,
            "step_id": cursor.step_id,
            "agent_id": "verify-qa",
            "verdict": "FAIL",
            "verdict_phase_epoch": str(cursor.phase_epoch),
        }
        if all(str(event.get(field) or "") == value for field, value in expected.items()):
            return event
        return None

    def _require_gate_pass(
        self,
        cursor: Cursor,
        transaction: StoreTransaction,
        *,
        gate_pass: GateVerdict | None,
    ) -> None:
        agent_id = self._required_gate_agent(cursor.phase)
        if agent_id is None:
            return
        if gate_pass is not None:
            if gate_pass.agent_id != agent_id:
                raise TransitionError(
                    f"wrong gate for {cursor.phase}: expected={agent_id}, received={gate_pass.agent_id}"
                )
            return
        latest_fail = transaction.latest_event("verdict_recorded")
        if latest_fail and all(
            str(latest_fail.get(field) or "") == expected
            for field, expected in (
                ("session_id", cursor.session_id),
                ("epic_id", cursor.epic_id),
                ("step_id", cursor.step_id),
                ("agent_id", agent_id),
            )
        ):
            verdict = str(latest_fail.get("verdict") or "FAIL")
            raise TransitionError(
                f"cannot finish {cursor.phase}: {agent_id} returned {verdict}; repair and re-verify are required"
            )
        raise TransitionError(
            f"cannot finish {cursor.phase}: {agent_id} PASS is required before finish"
        )

    def _finish_plan(
        self,
        cursor: Cursor,
        transaction: StoreTransaction,
        *,
        step_id: str | None,
        reason: str,
        event: dict[str, Any],
        gate_pass: GateVerdict | None = None,
    ) -> TransactionPlan:
        if cursor.status == CursorStatus.COMPLETE:
            return TransactionPlan(cursor, {"event": "finish_duplicate", "reason": "already complete"}, changed=False)
        if cursor.status == CursorStatus.HALTED:
            raise TransitionError("cannot finish a halted cursor")
        if step_id and step_id != cursor.step_id:
            raise TransitionError(f"finish step mismatch: cursor={cursor.step_id}, received={step_id}")

        queue = validate_decompose_tree(self.paths.project, cursor.role, cursor.epic_id) if cursor.phase == "DECOMPOSE" else self._queue(cursor)
        self._require_gate_pass(cursor, transaction, gate_pass=gate_pass)
        next_queue = queue
        mutations = []
        if cursor.phase in {"ANALYZE", "IMPLEMENT", "TASK", "REFACTOR"}:
            gate = self._analyze_gate(queue, force=cursor.phase == "ANALYZE")
            if gate["required"]:
                raise TransitionError(
                    f"cannot finish {cursor.phase}: ANALYZE gate {gate['reason']}"
                )
        if cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}:
            index_mutation = prepare_step_status(queue, cursor.step_id, "completed")
            mutations.append(index_mutation)
            next_queue = self._queue_after_step(queue, cursor.step_id)
        elif cursor.phase == "AUDIT":
            ready, audit_reason = audit_is_converged(self.paths.project, queue.role, queue.epic_id)
            if not ready:
                raise TransitionError(f"cannot finish AUDIT without a converged audit artifact: {audit_reason}")
        elif cursor.phase == "QA":
            artifacts = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
            verdict = qa_verdict(artifacts[-1]) if artifacts else None
            if verdict not in {"fail", "failed", "blocked", "pass", "passed", "complete", "completed"}:
                raise TransitionError("cannot finish QA without a valid verdict")
            if artifacts:
                previous = transaction.latest_event("verdict_accepted") or transaction.latest_event("finish")
                if previous and previous.get("source_phase") == "BUGFIX":
                    baseline = str(previous.get("qa_artifact_digest") or "")
                    current = file_digest(artifacts[-1]) or ""
                    if baseline and current == baseline:
                        raise TransitionError("cannot finish QA: qa_new_artifact_required")
            if verdict in {"fail", "failed", "blocked"}:
                queue_valid, queue_reason = bugfix_queue_intake(self.paths.project, queue.role, queue.epic_id)
                if not queue_valid:
                    raise TransitionError(f"cannot finish QA: {queue_reason}")
        elif cursor.phase == "BUGFIX":
            if not bugfix_report_paths(self.paths.project, queue.role, queue.epic_id):
                raise TransitionError("cannot finish BUGFIX without a bugfix artifact")
            queue_ready, queue_reason = bugfix_queue_state(self.paths.project, queue.role, queue.epic_id)
            if not queue_ready:
                raise TransitionError(f"cannot finish BUGFIX: {queue_reason}")

        if cursor.phase == "DECOMPOSE":
            phase, next_step, target_reason = "ANALYZE", "ANALYZE", "decompose index created"
        else:
            phase, next_step, target_reason = self._target(cursor, next_queue)
        candidate = self._copy_cursor(cursor)
        candidate.phase, candidate.step_id = phase, next_step
        candidate.status = CursorStatus.COMPLETE if phase == "DONE" else CursorStatus.ACTIVE
        candidate.attempt = 0
        candidate.failure = None
        candidate.phase_epoch += 1
        mutations.append(transaction.mutation(self.paths.active_context, self._render_body(candidate, next_queue)))
        transition_event = {
            **event,
            "reason": reason,
            "source_phase": cursor.phase,
            "source_step_id": cursor.step_id,
            "phase": phase,
            "step_id": next_step,
            "target_reason": target_reason,
        }
        if cursor.phase == "BUGFIX":
            qa_artifacts = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
            if qa_artifacts:
                transition_event["qa_artifact_digest"] = file_digest(qa_artifacts[-1])
        return TransactionPlan(candidate, transition_event, tuple(mutations))

    def start(self, epic_id: str, role: str = "back") -> Cursor:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current and current.status in {CursorStatus.ACTIVE, CursorStatus.RETRY}:
                if current.epic_id != epic_id or current.role != role:
                    raise TransitionError("cursor already owns another epic; finish or halt it first")
                return TransactionPlan(current, {"event": "start_duplicate"}, changed=False)
            if current and current.status == CursorStatus.HALTED and current.epic_id == epic_id and current.role == role:
                candidate = self._copy_cursor(current)
                candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
                candidate.status = CursorStatus.ACTIVE
                candidate.attempt = 0
                candidate.failure = None
                candidate.phase_epoch += 1
                queue = None if candidate.phase == "DECOMPOSE" else self._queue(candidate)
                pending_qa_failure = self._pending_qa_failure(transaction, current)
                if pending_qa_failure and self._qa_failure_ready(candidate):
                    route_key = (
                        f"{candidate.phase_epoch}:{candidate.epic_id}:{candidate.step_id}:"
                        f"qa-failure-resume:{pending_qa_failure.get('key') or 'recorded'}"
                    )
                    route_event = {
                        "event": "qa_failed",
                        "key": route_key,
                        "source": "resume-reconcile",
                        "agent_id": "verify-qa",
                        "verdict": "FAIL",
                        "session_id": candidate.session_id,
                        "epic_id": candidate.epic_id,
                        "step_id": candidate.step_id,
                        "verdict_step_id": candidate.step_id,
                        "verdict_phase_epoch": candidate.phase_epoch,
                        "recorded_at": pending_qa_failure.get("recorded_at") or "",
                        "reconciled_from": pending_qa_failure.get("key"),
                        "route": "BUGFIX",
                    }
                    gate_pass = GateVerdict(
                        schema="loop-gate-verdict/v1",
                        agent_id="verify-qa",
                        verdict="FAIL",
                        step_id=candidate.step_id,
                        session_id=candidate.session_id,
                        epic_id=candidate.epic_id,
                        recorded_at=pending_qa_failure.get("recorded_at") or "1970-01-01T00:00:00+00:00",
                    )
                    return self._finish_plan(
                        candidate,
                        transaction,
                        step_id=candidate.step_id,
                        reason="resume-reconcile:verify-qa:FAIL",
                        event=route_event,
                        gate_pass=gate_pass,
                    )
                return TransactionPlan(
                    candidate,
                    {
                        "event": "resume",
                        "epic_id": candidate.epic_id,
                        "role": candidate.role,
                        "phase": candidate.phase,
                        "step_id": candidate.step_id,
                        "reason": "resume halted cursor at saved phase",
                    },
                    (transaction.mutation(self.paths.active_context, self._render_body(candidate, queue)),),
                )
            candidate = Cursor(
                epic_id=epic_id,
                role=role,
                session_id=f"session-{uuid.uuid4().hex[:12]}",
                phase_epoch=1,
            )
            phase, step, reason = self._target(candidate)
            candidate.phase, candidate.step_id = phase, step
            candidate.status = CursorStatus.COMPLETE if phase == "DONE" else CursorStatus.ACTIVE
            return TransactionPlan(
                candidate,
                {"event": "start", "epic_id": epic_id, "role": role, "phase": phase, "step_id": step, "reason": reason},
                (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
            )

        result = self.store.transact(planner)
        if result.cursor is None:
            raise TransitionError("start transaction did not produce a cursor")
        return result.cursor

    def rewind(self, phase: str, *, reason: str = "manual rewind") -> Transition:
        target_phase = str(phase or "").strip().upper()
        if target_phase not in {"DECOMPOSE", "ANALYZE", "AUDIT", "QA", "BUGFIX"}:
            raise TransitionError(f"unsupported rewind phase: {phase!r}")

        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            queue = None if target_phase == "DECOMPOSE" else self._queue(current)
            candidate = self._copy_cursor(current)
            candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
            candidate.phase = target_phase
            candidate.step_id = target_phase
            candidate.status = CursorStatus.ACTIVE
            candidate.attempt = 0
            candidate.failure = None
            candidate.phase_epoch += 1
            event = {
                "event": "rewind",
                "reason": reason,
                "source_phase": current.phase,
                "source_step_id": current.step_id,
                "phase": target_phase,
                "step_id": target_phase,
            }
            return TransactionPlan(
                candidate,
                event,
                (transaction.mutation(self.paths.active_context, self._render_body(candidate, queue)),),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(result, event="rewind", reason=reason)

    def _transition_from_result(self, result: CommitResult, *, event: str, reason: str, metadata: dict[str, Any] | None = None) -> Transition:
        cursor = result.cursor
        if cursor is None:
            raise TransitionError("transaction did not return cursor")
        return Transition(
            event,
            reason,
            cursor.phase,
            cursor.step_id,
            cursor.status,
            cursor.attempt,
            result.changed,
            metadata or {},
            cursor.revision,
            result.tx_id,
        )

    def finish(self, *, step_id: str | None = None, reason: str = "session completed") -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            pending_qa_failure = self._pending_qa_failure(transaction, current)
            if pending_qa_failure and self._qa_failure_ready(current):
                route_key = (
                    f"{current.phase_epoch}:{current.epic_id}:{current.step_id}:"
                    f"qa-failure-finish:{pending_qa_failure.get('key') or 'recorded'}"
                )
                route_event = {
                    "event": "qa_failed",
                    "key": route_key,
                    "source": "finish-reconcile",
                    "agent_id": "verify-qa",
                    "verdict": "FAIL",
                    "session_id": current.session_id,
                    "epic_id": current.epic_id,
                    "step_id": current.step_id,
                    "verdict_step_id": current.step_id,
                    "verdict_phase_epoch": current.phase_epoch,
                    "recorded_at": pending_qa_failure.get("recorded_at") or "",
                    "reconciled_from": pending_qa_failure.get("key"),
                    "route": "BUGFIX",
                }
                gate_pass = GateVerdict(
                    schema="loop-gate-verdict/v1",
                    agent_id="verify-qa",
                    verdict="FAIL",
                    step_id=current.step_id,
                    session_id=current.session_id,
                    epic_id=current.epic_id,
                    recorded_at=pending_qa_failure.get("recorded_at") or "1970-01-01T00:00:00+00:00",
                )
                return self._finish_plan(
                    current,
                    transaction,
                    step_id=step_id,
                    reason="finish-reconcile:verify-qa:FAIL",
                    event=route_event,
                    gate_pass=gate_pass,
                )
            return self._finish_plan(current, transaction, step_id=step_id, reason=reason, event={"event": "finish"})

        result = self.store.transact(planner)
        return self._transition_from_result(result, event=str(result.event.get("event") or "finish"), reason=str(result.event.get("reason") or reason))

    def accept_verdict(self, record: GateVerdict, *, source: str = "subagent-stop", expected_agent_id: str | None = None) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            duplicate_fields = {
                "session_id": record.session_id,
                "epic_id": record.epic_id,
                "verdict_step_id": record.step_id,
                "agent_id": record.agent_id,
                "verdict": record.verdict,
                "recorded_at": record.recorded_at,
                "verdict_phase_epoch": current.phase_epoch,
            }
            duplicate = (
                transaction.event_with_fields("verdict_accepted", duplicate_fields)
                or transaction.event_with_fields("verdict_recorded", duplicate_fields)
                or transaction.event_with_fields("qa_failed", duplicate_fields)
            )
            if duplicate:
                if record.verdict == "FAIL" and current.phase == "QA" and self._qa_failure_ready(current):
                    route_key = (
                        f"{current.phase_epoch}:{record.session_id}:{record.epic_id}:{record.step_id}:"
                        f"qa-failure-reconcile:{record.recorded_at}"
                    )
                    if not transaction.event_seen("qa_failed", route_key):
                        route_event = {
                            "event": "qa_failed",
                            "key": route_key,
                            "source": "verdict-reconcile",
                            "agent_id": record.agent_id,
                            "verdict": record.verdict,
                            "session_id": record.session_id,
                            "epic_id": record.epic_id,
                            "step_id": record.step_id,
                            "verdict_step_id": record.step_id,
                            "verdict_phase_epoch": current.phase_epoch,
                            "recorded_at": record.recorded_at,
                            "reconciled_from": duplicate.get("key"),
                            "route": "BUGFIX",
                        }
                        return self._finish_plan(
                            current,
                            transaction,
                            step_id=record.step_id,
                            reason="verdict-reconcile:verify-qa:FAIL",
                            event=route_event,
                            gate_pass=record,
                        )
                return TransactionPlan(current, {"event": "verdict_duplicate"}, changed=False)
            if current.step_id != record.step_id:
                stale_duplicate_fields = dict(duplicate_fields)
                stale_duplicate_fields.pop("verdict_phase_epoch")
                stale_duplicate = (
                    transaction.event_with_fields("verdict_accepted", stale_duplicate_fields)
                    or transaction.event_with_fields("verdict_recorded", stale_duplicate_fields)
                    or transaction.event_with_fields("qa_failed", stale_duplicate_fields)
                )
                if stale_duplicate:
                    return TransactionPlan(current, {"event": "verdict_duplicate"}, changed=False)
            key = (
                f"{current.phase_epoch}:{record.session_id}:{record.epic_id}:"
                f"{record.step_id}:{record.agent_id}:{record.verdict}:{record.recorded_at}"
            )
            if (
                transaction.event_seen("verdict_accepted", key)
                or transaction.event_seen("verdict_recorded", key)
                or transaction.event_seen("qa_failed", key)
            ):
                return TransactionPlan(current, {"event": "verdict_duplicate", "key": key}, changed=False)
            if record.agent_id not in MANAGED_GATE_AGENTS:
                raise TransitionError(f"unsupported gate agent: {record.agent_id}")
            if expected_agent_id and record.agent_id != expected_agent_id:
                raise TransitionError(f"verdict agent mismatch: expected={expected_agent_id}, received={record.agent_id}")
            if current.epic_id != record.epic_id:
                raise TransitionError(f"verdict epic mismatch: cursor={current.epic_id}, received={record.epic_id}")
            if current.session_id != record.session_id:
                raise TransitionError("verdict session mismatch")
            if current.step_id != record.step_id:
                raise TransitionError(f"verdict step mismatch: cursor={current.step_id}, received={record.step_id}")
            required_agent = self._required_gate_agent(current.phase)
            if required_agent is None:
                raise TransitionError(f"no subagent gate is valid for phase {current.phase}")
            if record.agent_id != required_agent:
                raise TransitionError(
                    f"verdict agent mismatch for {current.phase}: expected={required_agent}, received={record.agent_id}"
                )
            event = {
                "event": "verdict_accepted" if record.verdict == "PASS" else "verdict_recorded",
                "key": key,
                "source": source,
                "phase": current.phase,
                "agent_id": record.agent_id,
                "verdict": record.verdict,
                "session_id": record.session_id,
                "epic_id": record.epic_id,
                "step_id": record.step_id,
                "verdict_step_id": record.step_id,
                "verdict_phase_epoch": current.phase_epoch,
                "recorded_at": record.recorded_at,
                "evidence_sha256": record.evidence_sha256,
            }
            if record.verdict != "PASS":
                if current.phase == "QA" and record.verdict == "FAIL":
                    if self._qa_failure_ready(current):
                        event["event"] = "qa_failed"
                        event["route"] = "BUGFIX"
                        return self._finish_plan(
                            current,
                            transaction,
                            step_id=record.step_id,
                            reason=f"{source}:{record.agent_id}:FAIL",
                            event=event,
                            gate_pass=record,
                        )
                return TransactionPlan(None, event)
            return self._finish_plan(
                current,
                transaction,
                step_id=record.step_id,
                reason=f"{source}:{record.agent_id}:PASS",
                event=event,
                gate_pass=record,
            )

        result = self.store.transact(planner)
        return self._transition_from_result(
            result,
            event=str(result.event.get("event") or "verdict_recorded"),
            reason=str(result.event.get("reason") or result.event.get("verdict") or "verdict"),
            metadata={"key": result.event.get("key"), "agent_id": result.event.get("agent_id"), "verdict": result.event.get("verdict")},
        )

    def reject_verdict(self, *, agent_id: str, diagnostic_codes: list[str] | tuple[str, ...], errors: list[str] | tuple[str, ...], source: str = "subagent-stop", max_retries: int = 2) -> tuple[int, bool]:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot reject a verdict without a cursor")
            prefix = f"{current.session_id}:{current.epic_id}:{current.step_id}:{agent_id}:"
            retry_number = transaction.event_count("verdict_rejected", prefix) + 1
            rejection = {
                "event": "verdict_rejected",
                "key": f"{prefix}{retry_number}",
                "source": source,
                "agent_id": agent_id,
                "phase": current.phase,
                "step_id": current.step_id,
                "retry": retry_number,
                "diagnostic_codes": list(diagnostic_codes),
                "errors": list(errors),
            }
            if retry_number <= max_retries:
                return TransactionPlan(None, rejection)
            candidate = self._copy_cursor(current)
            reason = f"schema_retry_exhausted:{agent_id}"
            candidate.status = CursorStatus.HALTED
            candidate.failure = self._failure("boundary", "schema_retry_exhausted", reason, retryable=False, attempt=candidate.attempt, details={"agent_id": agent_id})
            halt = {"event": "halt", "reason": reason, "phase": current.phase, "step_id": current.step_id}
            mutations = (transaction.mutation(self.paths.active_context, self._render_body(candidate)),)
            return TransactionPlan(candidate, halt, mutations, (rejection,))

        result = self.store.transact(planner)
        retry_number = int(result.event.get("retry") or max_retries + 1)
        return retry_number, bool(result.cursor and result.cursor.status == CursorStatus.HALTED)

    def record_event(self, event: dict[str, Any]) -> None:
        self.store.record_event(event)

    def retry(self, reason: str, *, expected_revision: int | None = None, details: dict[str, Any] | None = None) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot retry without cursor")
            if expected_revision is not None and current.revision != expected_revision:
                return TransactionPlan(current, {"event": "retry_skipped", "reason": "cursor advanced externally"}, changed=False)
            if current.status == CursorStatus.COMPLETE:
                raise TransitionError("cannot retry a complete cursor")
            if current.status == CursorStatus.HALTED:
                raise TransitionError("cannot retry a halted cursor")
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.RETRY
            candidate.attempt += 1
            candidate.failure = self._failure("session", "retry", reason, retryable=True, attempt=candidate.attempt, details=details)
            return TransactionPlan(
                candidate,
                {"event": "retry", "reason": reason, "phase": candidate.phase, "step_id": candidate.step_id, "attempt": candidate.attempt},
                (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(result, event=str(result.event.get("event") or "retry"), reason=str(result.event.get("reason") or reason))

    def halt(
        self,
        reason: str,
        *,
        expected_revision: int | None = None,
        details: dict[str, Any] | None = None,
        failure_category: str = "operator",
        failure_code: str = "halt",
    ) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot halt without cursor")
            if expected_revision is not None and current.revision != expected_revision:
                return TransactionPlan(current, {"event": "halt_skipped", "reason": "cursor advanced externally"}, changed=False)
            if current.status == CursorStatus.HALTED:
                return TransactionPlan(current, {"event": "halt_duplicate", "reason": reason}, changed=False)
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.HALTED
            candidate.failure = self._failure(failure_category, failure_code, reason, retryable=False, attempt=candidate.attempt, details=details)
            return TransactionPlan(
                candidate,
                {"event": "halt", "reason": reason, "phase": candidate.phase, "step_id": candidate.step_id},
                (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(result, event=str(result.event.get("event") or "halt"), reason=reason)

    def status(self) -> dict[str, Any]:
        cursor = self.store.read()
        if cursor is None:
            return {"ok": True, "status": "uninitialized", "cursor": None, "cursor_path": str(self.paths.cursor)}
        return {"ok": True, "status": cursor.status.value, "cursor": cursor.to_dict(), "cursor_path": str(self.paths.cursor)}

    def doctor(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ok": True, "cursor_path": str(self.paths.cursor), "active_context": str(self.paths.active_context), "journal_path": str(self.paths.events)}
        try:
            cursor = self.store.read()
            result["cursor"] = cursor.to_dict() if cursor else None
            if cursor:
                queue = self._queue(cursor)
                result["index"] = str(queue.path)
                result["pending_steps"] = [step.step_id for step in queue.pending]
        except Exception as exc:
            result.update({"ok": False, "error": str(exc)})
        return result
