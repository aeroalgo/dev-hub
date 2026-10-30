from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .boundary import BoundaryService
from .creative import (
    creative_finish_ready,
    phase_for_pending_step,
    resolve_creative_step,
)
from .implement_schema import complete_implement_artifact, validate_implement_artifact
from .security_schema import complete_security_artifact
from .index import (
    Queue,
    Step,
    bugfix_queue_path,
    bugfix_queue_intake,
    bugfix_report_paths,
    bugfix_queue_state,
    sync_bugfix_queue_evidence,
    implement_path,
    index_path,
    load_queue,
    phase_artifacts,
    plan_path,
    prepare_step_status,
    qa_pass_state,
    qa_verdict,
    queue_implement_gaps,
    queue_ready_for_qa,
    resolve_epic_kind,
    resolve_epic_role,
    validate_decompose_tree,
)
from .model import Cursor, CursorStatus, FailureRecord, Transition
from .store import CommitResult, LoopPaths, StoreTransaction, TransactionPlan, CursorStore, file_digest
from .verdict import ContextSyncResult, GateVerdict, MANAGED_GATE_AGENTS
from .roadmap import prepare_advance_after_context_sync


class TransitionError(RuntimeError):
    pass


_PHASE_GATE_AGENTS = {
    "DECOMPOSE": "verify-decompose",
    "IMPLEMENT": "verify-implement",
    "TASK": "verify-implement",
    "REFACTOR": "verify-implement",
    "SECURITY": "verify-security",
    "BUGFIX": "verify-bugfix",
    "QA": "verify-qa",
}

# Legacy cursors / env names may still carry these; loop never schedules them as live phases.
_OBSOLETE_PHASE_REMAP = {
    "ANALYZE": "DECOMPOSE",
    "AUDIT": "QA",
    "CONTEXT_SYNC": "QA",
}

_ENGINE_GATE_AGENTS = MANAGED_GATE_AGENTS | {"verify-security"}

# After this many failed verify(+repair) / schema / session attempts on one step → restart step.
MAX_VERIFY_REPAIR_CYCLES = 3
# After this many step restarts for the same epic+step → true halt (NEED_HUMAN).
MAX_STEP_RESTARTS = 3


class LoopEngine:
    """The domain facade; CursorStore owns every state mutation."""

    def __init__(self, paths: LoopPaths):
        self.paths = paths
        self.store = CursorStore(paths)
        self.boundary = BoundaryService(paths)

    def _queue(self, cursor: Cursor) -> Queue:
        return load_queue(self.paths.project, cursor.role, cursor.epic_id, kind=cursor.kind)

    def _plan_path(self, cursor: Cursor) -> Path:
        return plan_path(self.paths.project, cursor.role, cursor.epic_id, kind=cursor.kind or "feature")

    def _phase_after_queue(
        self,
        queue: Queue,
        *,
        context_sync_completed: bool = False,
    ) -> tuple[str, str]:
        if getattr(queue, "kind", None) == "security":
            return "DONE", "security audit queue complete"
        ready, implement_reason = queue_ready_for_qa(self.paths.project, queue)
        if not ready:
            raise TransitionError(f"cannot advance past IMPLEMENT: {implement_reason}")
        qa = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
        bugfix_queue = bugfix_queue_path(self.paths.project, queue.role, queue.epic_id)
        if not qa:
            return "QA", "qa artifact required"
        verdict = qa_verdict(qa[-1])
        if verdict in {"fail", "failed", "blocked"}:
            queue_ready, _ = bugfix_queue_state(self.paths.project, queue.role, queue.epic_id)
            if bugfix_queue.is_file() and queue_ready:
                return "QA", "bugfix exists; re-qa required"
            return "BUGFIX", "qa failed"
        if verdict in {"pass", "passed", "complete", "completed"}:
            if context_sync_completed:
                return "DONE", "qa passed; context-sync completed"
            return "QA", "qa passed; context-sync result required before finish"
        return "QA", "qa verdict missing"

    def _work_steps(self, queue: Queue) -> tuple[Step, ...]:
        """Pending index steps, or completed-without-implement gaps (fail-closed recovery)."""
        if queue.pending:
            return queue.pending
        if getattr(queue, "kind", None) == "security":
            return ()
        return tuple(step for step, _reason in queue_implement_gaps(self.paths.project, queue))

    def _has_implementation_progress(self, queue: Queue) -> bool:
        kind = getattr(queue, "kind", None) or "feature"
        return any(
            implement_path(
                self.paths.project,
                queue.role,
                queue.epic_id,
                step,
                kind=kind,
            ).is_file()
            for step in queue.steps
        )

    def _target(
        self,
        cursor: Cursor,
        queue: Queue | None = None,
        *,
        context_sync_completed: bool = False,
        decompose_verified: bool = False,
    ) -> tuple[str, str, str]:
        if queue is None:
            canonical_index = index_path(self.paths.project, cursor.role, cursor.epic_id, kind=cursor.kind or "feature")
            if not canonical_index.is_file():
                plan = self._plan_path(cursor)
                if not plan.is_file():
                    raise FileNotFoundError(f"canonical plan missing: {plan}")
                return "DECOMPOSE", "DECOMPOSE", f"canonical decompose index pending: {canonical_index}"
            active_queue = self._queue(cursor)
        else:
            active_queue = queue
        work = self._work_steps(active_queue)
        if work:
            if (
                cursor.phase in {"", "DECOMPOSE"}
                and getattr(active_queue, "kind", None) != "security"
                and cursor.kind != "security"
                and not decompose_verified
                and not self._has_implementation_progress(active_queue)
            ):
                return "DECOMPOSE", "DECOMPOSE", "decompose closure gate required"
            step = work[0]
            phase, reason = phase_for_pending_step(self.paths.project, active_queue, step)
            if step.status in {"completed", "done"} and step not in active_queue.pending:
                reason = (
                    f"implement incomplete for {step.step_id}: index status {step.status!r} "
                    "without completed implement artifact"
                )
            return phase, step.step_id, reason
        phase, reason = self._phase_after_queue(
            active_queue,
            context_sync_completed=context_sync_completed,
        )
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
        if queue is None and cursor.phase not in {"DECOMPOSE", "BUGFIX"} and cursor.epic_id:
            try:
                queue = self._queue(cursor)
            except Exception:
                queue = None
        if cursor.phase == "BUGFIX":
            load_path = bugfix_queue_path(self.paths.project, cursor.role, cursor.epic_id)
        elif cursor.phase == "SECURITY" and queue is not None:
            load_path = None
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
        ]
        next_load_number = 1
        if load_path is not None:
            lines.append(
                f"{next_load_number}. {load_path.relative_to(self.paths.project).as_posix()} — "
                f"{'queue/status' if queue is not None else 'source plan'}"
            )
            next_load_number += 1
        phase_directories = {
            "CREATIVE": "creative",
            "QA": "qa",
            "BUGFIX": "bugfix",
        }
        artifact_kind = phase_directories.get(cursor.phase)
        if artifact_kind:
            lines.append(
                f"{next_load_number}. memory-bank/{cursor.role}/{artifact_kind}/{cursor.epic_id}/ — current phase artifacts"
            )
            next_load_number += 1
        if queue is not None and cursor.step_id and cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR", "CREATIVE", "SECURITY"}:
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step and step.shard:
                shard_rel = step.shard
                if not shard_rel.startswith("memory-bank/"):
                    shard_candidate = queue.path.parent / "steps" / Path(step.shard).name
                    if shard_candidate.is_file():
                        shard_rel = shard_candidate.relative_to(self.paths.project).as_posix()
                lines.append(f"{next_load_number}. {shard_rel} — current step artifact")
                next_load_number += 1
            if step and cursor.phase != "CREATIVE":
                impl_label = "security execute artifact" if cursor.phase == "SECURITY" else "implement artifact"
                lines.append(
                    f"{next_load_number}. {implement_path(self.paths.project, queue.role, queue.epic_id, step, kind=cursor.kind or "feature").relative_to(self.paths.project).as_posix()} — {impl_label}"
                )
                next_load_number += 1
            if cursor.phase == "SECURITY" and queue is not None:
                lines.append(
                    f"{next_load_number}. {queue.path.relative_to(self.paths.project).as_posix()} — decompose index status"
                )
                next_load_number += 1
        if next_load_number == 1:
            fallback = self._plan_path(cursor)
            lines.append(f"1. {fallback.relative_to(self.paths.project).as_posix()} — source plan")
        handoff = (
            "- After the queue is closed, accepted verify-bugfix PASS atomically advances "
            "BUGFIX to QA; do not call finish --step BUGFIX afterward."
            if cursor.phase == "BUGFIX"
            else f"- Finish with: `python3 $DEV_HUB/bin/loop.py finish --project {self.paths.project} --step {cursor.step_id}`."
        )
        lines.extend(
            [
                "",
                f"## Handoff {cursor.phase}",
                f"- Current cursor: `{cursor.epic_id}/{cursor.phase}/{cursor.step_id}`.",
                "- This file is generated by loop/kernel; do not edit it as state.",
                handoff,
                "",
                self.boundary.context(cursor),
            ]
        )
        return "\n".join(lines) + "\n"

    def _render_restart_body(self, cursor: Cursor, *, reason: str, restart_number: int) -> str:
        body = self._render_body(cursor)
        banner = (
            f"\n## STEP RESTART ({restart_number}/{MAX_STEP_RESTARTS})\n"
            f"- Reason: {reason}\n"
            f"- Same step `{cursor.step_id}` starts from scratch with a new session_id / GATE_IDENTITY.\n"
            "- Discard prior partial session claims (OK/Готово without accepted gate PASS).\n"
            "- Re-read the work shard; re-implement / re-decompose as required; then spawn the gate once.\n"
            f"- After {MAX_STEP_RESTARTS} step restarts without progress the cursor HALTs (NEED_HUMAN).\n"
        )
        # Insert banner after the Handoff section header block.
        marker = f"## Handoff {cursor.phase}\n"
        if marker in body:
            return body.replace(marker, marker + banner.lstrip("\n"), 1)
        return body + banner

    @staticmethod
    def _failure(category: str, code: str, message: str, *, retryable: bool, attempt: int, details: dict[str, Any] | None = None) -> FailureRecord:
        return FailureRecord(category, code, message, retryable, attempt, details=details or {})

    @staticmethod
    def _required_gate_agent(phase: str) -> str | None:
        return _PHASE_GATE_AGENTS.get(str(phase or "").upper())

    @staticmethod
    def _remap_obsolete_phase(phase: str) -> str:
        key = str(phase or "").strip().upper()
        return _OBSOLETE_PHASE_REMAP.get(key, key)

    def _normalize_obsolete_cursor(self, cursor: Cursor) -> Cursor:
        """Normalize cursors written by versions that had removed phases."""
        remapped = self._remap_obsolete_phase(cursor.phase)
        if remapped == cursor.phase:
            return cursor
        candidate = self._copy_cursor(cursor)
        candidate.phase = remapped
        if remapped in {"DECOMPOSE", "QA", "BUGFIX"}:
            candidate.step_id = remapped
        candidate.phase_epoch += 1
        return candidate

    def _qa_failure_ready(self, cursor: Cursor) -> bool:
        artifacts = phase_artifacts(self.paths.project, cursor.role, cursor.epic_id, "qa")
        qa_status = qa_verdict(artifacts[-1]) if artifacts else None
        synced, _reason = sync_bugfix_queue_evidence(
            self.paths.project,
            cursor.role,
            cursor.epic_id,
        )
        if not synced:
            return False
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
    def _event_matches_cursor(
        event: dict[str, Any] | None,
        cursor: Cursor,
        *,
        event_name: str,
        agent_id: str | None = None,
    ) -> bool:
        if event is None or str(event.get("event") or "") != event_name:
            return False
        expected = {
            "session_id": cursor.session_id,
            "epic_id": cursor.epic_id,
            "step_id": cursor.step_id,
        }
        if not all(str(event.get(field) or "") == str(value) for field, value in expected.items()):
            return False
        event_epoch = event.get("phase_epoch", event.get("verdict_phase_epoch"))
        if str(event_epoch or "") != str(cursor.phase_epoch):
            return False
        return agent_id is None or str(event.get("agent_id") or "") == agent_id

    def _qa_pass_event(
        self,
        transaction: StoreTransaction,
        cursor: Cursor,
    ) -> dict[str, Any] | None:
        event = transaction.latest_event("verdict_accepted")
        if not self._event_matches_cursor(
            event,
            cursor,
            event_name="verdict_accepted",
            agent_id="verify-qa",
        ):
            return None
        if str(event.get("verdict") or "") != "PASS" or str(event.get("phase") or "") != "QA":
            return None
        return event

    @staticmethod
    def _event_timestamp(event: dict[str, Any]) -> float | None:
        for field in ("recorded_at", "at"):
            raw = str(event.get(field) or "").strip()
            if not raw:
                continue
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.timestamp()
        return None

    def _historical_qa_pass_event(
        self,
        transaction: StoreTransaction,
        cursor: Cursor,
    ) -> dict[str, Any] | None:
        if cursor.phase != "QA" or cursor.step_id != "QA":
            return None
        event = transaction.event_with_fields(
            "verdict_accepted",
            {
                "phase": "QA",
                "agent_id": "verify-qa",
                "verdict": "PASS",
                "context_sync_required": True,
                "epic_id": cursor.epic_id,
                "step_id": "QA",
            },
        )
        return event

    def _qa_pass_resume_allowed(
        self,
        transaction: StoreTransaction,
        cursor: Cursor,
        pass_event: dict[str, Any],
    ) -> tuple[bool, str | None, str | None]:
        if not self._qa_pass_ready(cursor):
            return False, None, None
        artifacts = phase_artifacts(self.paths.project, cursor.role, cursor.epic_id, "qa")
        if not artifacts:
            return False, None, None
        latest_artifact = artifacts[-1]
        current_digest = file_digest(latest_artifact)
        try:
            current_path = latest_artifact.resolve().relative_to(self.paths.project.resolve()).as_posix()
            artifact_timestamp = latest_artifact.stat().st_mtime
        except (OSError, ValueError):
            return False, None, None
        event_timestamp = self._event_timestamp(pass_event)
        if event_timestamp is None or artifact_timestamp > event_timestamp + 1.0:
            return False, None, None
        recorded_digest = str(pass_event.get("qa_artifact_digest") or "")
        if recorded_digest:
            if not current_digest or current_digest != recorded_digest:
                return False, None, None
        recorded_path = str(pass_event.get("qa_artifact_path") or "")
        if recorded_path and recorded_path != current_path:
            return False, None, None

        failure_fields = {
            "phase": "QA",
            "agent_id": "verify-qa",
            "verdict": "FAIL",
            "epic_id": cursor.epic_id,
            "step_id": "QA",
        }
        for event_name in ("verdict_recorded", "qa_failed"):
            failure = transaction.event_with_fields(event_name, failure_fields)
            if failure is None:
                continue
            failure_timestamp = self._event_timestamp(failure)
            pass_timestamp = self._event_timestamp(pass_event)
            if (
                failure_timestamp is None
                or pass_timestamp is None
                or failure_timestamp > pass_timestamp
            ):
                return False, None, None

        bugfix_finish = transaction.event_with_fields(
            "finish",
            {"source_phase": "BUGFIX", "epic_id": cursor.epic_id},
        )
        if bugfix_finish is not None:
            finish_timestamp = self._event_timestamp(bugfix_finish)
            pass_timestamp = self._event_timestamp(pass_event)
            if (
                finish_timestamp is None
                or pass_timestamp is None
                or finish_timestamp > pass_timestamp
            ):
                return False, None, None
        return True, current_digest, current_path

    def _context_sync_event(
        self,
        transaction: StoreTransaction,
        cursor: Cursor,
    ) -> dict[str, Any] | None:
        event = transaction.latest_event("context_sync_completed")
        if not self._event_matches_cursor(
            event,
            cursor,
            event_name="context_sync_completed",
            agent_id="context-sync",
        ):
            return None
        if str(event.get("status") or "") != "done":
            return None
        return event

    def _context_sync_path(self, cursor: Cursor, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.paths.project / candidate
        candidate = candidate.resolve()
        root = (
            self.paths.project
            / "memory-bank"
            / cursor.role
            / "context-sync"
            / cursor.epic_id
        ).resolve()
        if candidate.parent != root or not candidate.name.startswith("sync-") or candidate.suffix != ".md":
            raise TransitionError(
                "context-sync sync_path must be a sync-*.md file under "
                f"memory-bank/{cursor.role}/context-sync/{cursor.epic_id}/"
            )
        if not candidate.is_file():
            raise TransitionError(f"context-sync artifact missing: {candidate}")
        return candidate

    def _qa_pass_ready(self, cursor: Cursor) -> bool:
        if cursor.phase != "QA":
            return False
        ready, _reason = qa_pass_state(self.paths.project, cursor.role, cursor.epic_id)
        return ready

    def _context_sync_ready(self, cursor: Cursor) -> bool:
        if cursor.phase != "QA":
            return False
        event = self.store.latest_event("context_sync_completed")
        return self._event_matches_cursor(
            event,
            cursor,
            event_name="context_sync_completed",
            agent_id="context-sync",
        ) and str(event.get("status") or "") == "done"

    def qa_context_sync_pending(self, cursor: Cursor) -> bool:
        if cursor.phase != "QA":
            return False
        event = self.store.latest_event("verdict_accepted")
        if not self._event_matches_cursor(
            event,
            cursor,
            event_name="verdict_accepted",
            agent_id="verify-qa",
        ):
            return False
        return (
            str(event.get("verdict") or "") == "PASS"
            and bool(event.get("context_sync_required"))
            and not self._context_sync_ready(cursor)
        )

    def _salvage_gate_pass_from_pre_emit(self, cursor: Cursor) -> GateVerdict | None:
        """Reuse a validate-verdict stamp when the child fence was rejected for format noise."""
        agent_id = self._required_gate_agent(cursor.phase)
        if agent_id is None:
            return None
        from .pre_emit import read_pre_emit_stamp

        stamp = read_pre_emit_stamp(
            self.paths,
            session_id=cursor.session_id,
            agent_id=agent_id,
            step_id=cursor.step_id,
        )
        if stamp is None or not isinstance(stamp.payload, dict):
            return None
        payload = dict(stamp.payload)
        if str(payload.get("verdict") or "").upper() != "PASS":
            return None
        if str(payload.get("session_id") or "") != cursor.session_id:
            return None
        if str(payload.get("epic_id") or "") != cursor.epic_id:
            return None
        if str(payload.get("step_id") or "") != cursor.step_id:
            return None
        if str(payload.get("agent_id") or "") != agent_id:
            return None
        try:
            return GateVerdict.model_validate(payload)
        except Exception:
            return None

    def try_session_auto_finish(self, cursor: Cursor) -> Transition | None:
        """Machine-close a phase when artifacts prove done but the agent skipped finish.

        Order:
        1) Salvage validate-verdict PASS stamp → accept_verdict (atomic gate close).
        2) Phase-specific artifact auto-finish (QA-fail / BUGFIX / CREATIVE).
        """
        if cursor.status in {CursorStatus.COMPLETE, CursorStatus.HALTED}:
            return None

        gate_agent = self._required_gate_agent(cursor.phase)
        if gate_agent is not None:
            salvaged = self._salvage_gate_pass_from_pre_emit(cursor)
            if salvaged is not None:
                # Phase artifact gates still apply inside accept_verdict/_finish_plan.
                if cursor.phase == "QA" and not self._qa_pass_ready(cursor) and not self._qa_failure_ready(cursor):
                    salvaged = None
                if salvaged is not None:
                    try:
                        transition = self.accept_verdict(
                            salvaged,
                            source="session-auto-finish:pre-emit-pass",
                            expected_agent_id=gate_agent,
                        )
                    except TransitionError:
                        transition = None
                    if transition is not None and transition.changed:
                        return transition

        if cursor.phase == "QA" and self._qa_failure_ready(cursor):
            try:
                return self.finish(step_id=cursor.step_id, reason="session-auto-finish:qa-fail")
            except TransitionError:
                return None

        if cursor.phase == "BUGFIX" and self._bugfix_ready_to_finish(cursor):
            try:
                return self.finish(step_id=cursor.step_id, reason="session-auto-finish:bugfix")
            except TransitionError:
                return None

        if cursor.phase == "CREATIVE":
            try:
                queue = self._queue(cursor)
                step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
                if step is None:
                    return None
                ready, _ = creative_finish_ready(self.paths.project, queue, step)
                if not ready:
                    return None
                return self.finish(step_id=cursor.step_id, reason="session-auto-finish:creative")
            except TransitionError:
                return None

        return None

    def _bugfix_ready_to_finish(self, cursor: Cursor) -> bool:
        if cursor.phase != "BUGFIX":
            return False
        synced, _reason = sync_bugfix_queue_evidence(
            self.paths.project,
            cursor.role,
            cursor.epic_id,
        )
        if not synced:
            return False
        ready, reason = bugfix_queue_state(self.paths.project, cursor.role, cursor.epic_id)
        return ready and reason == "bugfix_queue_ready"

    def rearm_active(self, *, reason: str, expected_revision: int | None = None) -> Transition:
        """Keep the same phase after expected partial progress; clear retry streak."""

        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot rearm without cursor")
            if expected_revision is not None and current.revision != expected_revision:
                return TransactionPlan(current, {"event": "rearm_skipped", "reason": "cursor advanced externally"}, changed=False)
            if current.status == CursorStatus.COMPLETE:
                raise TransitionError("cannot rearm a complete cursor")
            if current.status == CursorStatus.HALTED:
                raise TransitionError("cannot rearm a halted cursor")
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.ACTIVE
            candidate.attempt = 0
            candidate.failure = None
            return TransactionPlan(
                candidate,
                {
                    "event": "rearm_active",
                    "reason": reason,
                    "phase": candidate.phase,
                    "step_id": candidate.step_id,
                },
                (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(
            result,
            event=str(result.event.get("event") or "rearm_active"),
            reason=str(result.event.get("reason") or reason),
        )

    def restart_step(
        self,
        reason: str,
        *,
        expected_revision: int | None = None,
        details: dict[str, Any] | None = None,
        allow_halted: bool = False,
    ) -> Transition:
        """Restart the same epic/phase/step from scratch after exhausted verify/repair cycles.

        New session_id + phase_epoch; attempt reset. After MAX_STEP_RESTARTS → halt.
        """

        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot restart step without cursor")
            if expected_revision is not None and current.revision != expected_revision:
                return TransactionPlan(
                    current, {"event": "step_restart_skipped", "reason": "cursor advanced externally"}, changed=False
                )
            if current.status == CursorStatus.COMPLETE:
                raise TransitionError("cannot restart a complete cursor")
            if current.status == CursorStatus.HALTED and not allow_halted:
                raise TransitionError("cannot restart a halted cursor")
            restart_prefix = f"{current.epic_id}:{current.step_id}:"
            restart_number = transaction.event_count("step_restarted", restart_prefix) + 1
            if restart_number > MAX_STEP_RESTARTS:
                candidate = self._copy_cursor(current)
                halt_reason = (
                    f"step_restart_exhausted:{current.step_id} after {MAX_STEP_RESTARTS} "
                    f"restarts ({reason})"
                )
                candidate.status = CursorStatus.HALTED
                candidate.failure = self._failure(
                    "session",
                    "step_restart_exhausted",
                    halt_reason,
                    retryable=False,
                    attempt=candidate.attempt,
                    details={"prior_reason": reason, **(details or {})},
                )
                return TransactionPlan(
                    candidate,
                    {
                        "event": "halt",
                        "reason": halt_reason,
                        "phase": candidate.phase,
                        "step_id": candidate.step_id,
                    },
                    (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
                )
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.ACTIVE
            candidate.attempt = 0
            candidate.failure = None
            candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
            candidate.phase_epoch += 1
            event = {
                "event": "step_restarted",
                "key": f"{restart_prefix}{restart_number}",
                "reason": reason,
                "phase": candidate.phase,
                "step_id": candidate.step_id,
                "epic_id": candidate.epic_id,
                "restart": restart_number,
                "session_id": candidate.session_id,
                "phase_epoch": candidate.phase_epoch,
                "details": details or {},
            }
            return TransactionPlan(
                candidate,
                event,
                (
                    transaction.mutation(
                        self.paths.active_context,
                        self._render_restart_body(
                            candidate, reason=reason, restart_number=restart_number
                        ),
                    ),
                ),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(
            result,
            event=str(result.event.get("event") or "step_restarted"),
            reason=str(result.event.get("reason") or reason),
            metadata={
                "restart": result.event.get("restart"),
                "session_id": result.event.get("session_id"),
                "phase_epoch": result.event.get("phase_epoch"),
            },
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
        if cursor.phase == "DECOMPOSE":
            if (
                gate_pass is not None
                and gate_pass.agent_id == "verify-decompose"
                and gate_pass.verdict == "PASS"
            ):
                return
            raise TransitionError(
                "cannot finish DECOMPOSE: accepted verify-decompose PASS is required"
            )
        agent_id = self._required_gate_agent(cursor.phase)
        if agent_id is None:
            return
        if gate_pass is not None:
            if gate_pass.agent_id != agent_id:
                raise TransitionError(
                    f"wrong gate for {cursor.phase}: expected={agent_id}, received={gate_pass.agent_id}"
                )
            return
        if cursor.phase == "QA" and self._qa_pass_event(transaction, cursor) is not None:
            return
        if cursor.phase == "QA" and self._qa_failure_ready(cursor):
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
            if cursor.phase == "QA" and agent_id == "verify-qa":
                raise TransitionError(
                    "cannot finish QA: verify-qa FAIL is recorded but qa-*.yaml "
                    "(verdict: fail|blocked) and open bugfix-queue.yaml are required; "
                    "write them then call finish to route BUGFIX — do not gate-repair a product QA FAIL"
                )
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
        context_sync_path: str | None = None,
    ) -> TransactionPlan:
        if cursor.status == CursorStatus.COMPLETE:
            return TransactionPlan(cursor, {"event": "finish_duplicate", "reason": "already complete"}, changed=False)
        if cursor.status == CursorStatus.HALTED:
            raise TransitionError(
                "cannot finish a halted cursor; resume it first with "
                f"`python3 {self.paths.hub / 'bin' / 'loop.py'} start "
                f"--project {self.paths.project} --epic {cursor.epic_id} --role {cursor.role}`, "
                "then continue the current phase under the new GATE_IDENTITY"
            )
        if step_id and step_id != cursor.step_id:
            if step_id == "BUGFIX" and cursor.phase == "QA":
                raise TransitionError(
                    "BUGFIX already completed by the accepted verify-bugfix PASS; "
                    "the current phase is QA, so do not call finish --step BUGFIX again"
                )
            raise TransitionError(f"finish step mismatch: cursor={cursor.step_id}, received={step_id}")

        if cursor.phase == "DECOMPOSE":
            try:
                queue = validate_decompose_tree(
                    self.paths.project,
                    cursor.role,
                    cursor.epic_id,
                    require_fresh_pending=True,
                )
            except (ValueError, FileNotFoundError, OSError) as exc:
                raise TransitionError(
                    f"cannot finish DECOMPOSE: invalid yaml tree — {exc}"
                ) from exc
        else:
            queue = self._queue(cursor)
        self._require_gate_pass(cursor, transaction, gate_pass=gate_pass)
        next_queue = queue
        mutations = []
        if cursor.phase == "CREATIVE":
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step is None:
                raise TransitionError(
                    f"cannot finish CREATIVE: step {cursor.step_id!r} missing from decompose index"
                )
            ready, creative_reason = creative_finish_ready(self.paths.project, queue, step)
            if not ready:
                raise TransitionError(f"cannot finish CREATIVE: {creative_reason}")
        resolved_context_sync_path = context_sync_path
        if cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}:
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step is None:
                raise TransitionError(
                    f"cannot finish {cursor.phase}: step {cursor.step_id!r} missing from decompose index"
                )
            try:
                # Machine-owned status write: step completed + all cp done.
                # Agents never invent status literals — finish is the sole writer.
                complete_implement_artifact(
                    implement_path(self.paths.project, queue.role, queue.epic_id, step),
                    expected_step_id=cursor.step_id,
                    expected_plan_id=queue.epic_id,
                )
            except (ValueError, FileNotFoundError, OSError) as exc:
                raise TransitionError(
                    f"cannot finish {cursor.phase}: invalid implement artifact — {exc}"
                ) from exc
            index_mutation = prepare_step_status(queue, cursor.step_id, "completed")
            mutations.append(index_mutation)
            next_queue = self._queue_after_step(queue, cursor.step_id)
        elif cursor.phase == "SECURITY":
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step is None:
                raise TransitionError(
                    f"cannot finish SECURITY: step {cursor.step_id!r} missing from decompose index"
                )
            try:
                complete_security_artifact(
                    implement_path(
                        self.paths.project,
                        queue.role,
                        queue.epic_id,
                        step,
                        kind=cursor.kind or "security",
                    ),
                    expected_step_id=cursor.step_id,
                    expected_plan_id=queue.epic_id,
                )
            except (ValueError, FileNotFoundError, OSError) as exc:
                raise TransitionError(
                    f"cannot finish SECURITY: invalid security artifact — {exc}"
                ) from exc
            index_mutation = prepare_step_status(queue, cursor.step_id, "completed")
            mutations.append(index_mutation)
            next_queue = self._queue_after_step(queue, cursor.step_id)
        elif cursor.phase == "QA":
            artifacts = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
            verdict = qa_verdict(artifacts[-1]) if artifacts else None
            if verdict not in {"fail", "failed", "blocked", "pass", "passed", "complete", "completed"}:
                raise TransitionError(
                    "qa_artifact_required_before_pass: write memory-bank/<role>/qa/<epic>/qa-*.yaml "
                    "with verdict pass|fail|blocked BEFORE verify-qa PASS can atomically finish; "
                    "cannot finish QA without a valid qa artifact verdict"
                )
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
            elif verdict in {"pass", "passed", "complete", "completed"}:
                runtime_ready, runtime_reason = qa_pass_state(
                    self.paths.project,
                    queue.role,
                    queue.epic_id,
                )
                if not runtime_ready:
                    raise TransitionError(f"cannot finish QA pass: {runtime_reason}")
                if resolved_context_sync_path is None:
                    sync_event = self._context_sync_event(transaction, cursor)
                    if sync_event is not None:
                        resolved_context_sync_path = str(sync_event.get("sync_path") or "")
                if not resolved_context_sync_path:
                    raise TransitionError(
                        "cannot finish QA pass before context-sync completion: spawn agent_type=context-sync "
                        f"then write memory-bank/{queue.role}/context-sync/{queue.epic_id}/sync-*.md"
                    )
                self._context_sync_path(cursor, resolved_context_sync_path)
        elif cursor.phase == "BUGFIX":
            if not bugfix_report_paths(self.paths.project, queue.role, queue.epic_id):
                raise TransitionError("cannot finish BUGFIX without a bugfix artifact")
            synced, sync_reason = sync_bugfix_queue_evidence(
                self.paths.project,
                queue.role,
                queue.epic_id,
            )
            if not synced:
                raise TransitionError(f"cannot finish BUGFIX: {sync_reason}")
            queue_ready, queue_reason = bugfix_queue_state(self.paths.project, queue.role, queue.epic_id)
            if not queue_ready:
                raise TransitionError(f"cannot finish BUGFIX: {queue_reason}")
        if cursor.phase == "DECOMPOSE":
            phase, next_step, target_reason = self._target(
                cursor,
                next_queue,
                decompose_verified=True,
            )
        elif cursor.phase == "CREATIVE":
            phase, next_step, target_reason = self._target(cursor, next_queue)
            if phase == "CREATIVE":
                raise TransitionError(
                    "cannot finish CREATIVE: open creative gate still routes to CREATIVE "
                    "(close needs_creative on the work shard before finish)"
                )
        else:
            phase, next_step, target_reason = self._target(
                cursor,
                next_queue,
                context_sync_completed=(
                    cursor.phase == "QA" and resolved_context_sync_path is not None
                ),
            )
        candidate = self._copy_cursor(cursor)
        candidate.phase, candidate.step_id = phase, next_step
        candidate.status = CursorStatus.COMPLETE if phase == "DONE" else CursorStatus.ACTIVE
        candidate.attempt = 0
        candidate.failure = None
        candidate.phase_epoch += 1
        transition_event = {
            **event,
            "reason": reason,
            "source_phase": cursor.phase,
            "source_step_id": cursor.step_id,
            "phase": phase,
            "step_id": next_step,
            "target_reason": target_reason,
        }
        render_queue = next_queue

        if cursor.phase == "QA" and phase == "DONE":
            try:
                advance = prepare_advance_after_context_sync(
                    self.paths.project,
                    role=cursor.role,
                    epic_id=cursor.epic_id,
                )
            except ValueError as exc:
                raise TransitionError(f"cannot finish QA (roadmap advance): {exc}") from exc
            if advance.queue_body and advance.queue_path is not None:
                mutations.append(transaction.mutation(advance.queue_path, advance.queue_body))
            transition_event["roadmap_marked"] = advance.marked
            transition_event["roadmap_skipped"] = advance.skipped
            if advance.blocked_reason:
                transition_event["roadmap_blocked"] = advance.blocked_reason
            if advance.next_epic_id and not advance.complete:
                candidate.epic_id = advance.next_epic_id
                candidate.role = cursor.role
                candidate.kind = advance.next_kind or "feature"
                candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
                try:
                    phase, next_step, target_reason = self._target(candidate)
                except FileNotFoundError as exc:
                    raise TransitionError(f"cannot advance roadmap: {exc}") from exc
                candidate.phase, candidate.step_id = phase, next_step
                candidate.status = CursorStatus.ACTIVE
                transition_event["phase"] = phase
                transition_event["step_id"] = next_step
                transition_event["target_reason"] = f"roadmap advance → {advance.next_epic_id}: {target_reason}"
                transition_event["next_epic_id"] = advance.next_epic_id
                transition_event["next_kind"] = advance.next_kind
                render_queue = None
                try:
                    render_queue = self._queue(candidate)
                except Exception:
                    render_queue = None

        mutations.append(transaction.mutation(self.paths.active_context, self._render_body(candidate, render_queue)))
        if cursor.phase == "BUGFIX":
            qa_artifacts = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
            if qa_artifacts:
                transition_event["qa_artifact_digest"] = file_digest(qa_artifacts[-1])
        return TransactionPlan(candidate, transition_event, tuple(mutations))

    def start(self, epic_id: str, role: str = "auto") -> Cursor:
        role = resolve_epic_role(self.paths.project, epic_id, role)

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
                if self._remap_obsolete_phase(candidate.phase) != candidate.phase:
                    candidate = self._normalize_obsolete_cursor(candidate)
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
                historical_qa_pass = self._historical_qa_pass_event(transaction, current)
                if historical_qa_pass is not None:
                    pass_allowed, qa_artifact_digest, qa_artifact_path = self._qa_pass_resume_allowed(
                        transaction,
                        current,
                        historical_qa_pass,
                    )
                    if pass_allowed:
                        reconcile_key = (
                            f"{candidate.phase_epoch}:{candidate.session_id}:{candidate.epic_id}:"
                            f"{candidate.step_id}:verify-qa:PASS:resume:{historical_qa_pass.get('key') or 'legacy'}"
                        )
                        reconcile_event = {
                            "event": "verdict_accepted",
                            "key": reconcile_key,
                            "source": "resume-reconcile",
                            "phase": candidate.phase,
                            "agent_id": "verify-qa",
                            "verdict": "PASS",
                            "context_sync_required": True,
                            "session_id": candidate.session_id,
                            "epic_id": candidate.epic_id,
                            "step_id": candidate.step_id,
                            "verdict_step_id": candidate.step_id,
                            "verdict_phase_epoch": candidate.phase_epoch,
                            "recorded_at": historical_qa_pass.get("recorded_at") or "",
                            "evidence_sha256": historical_qa_pass.get("evidence_sha256"),
                            "qa_artifact_digest": qa_artifact_digest,
                            "qa_artifact_path": qa_artifact_path,
                            "target_reason": "qa pass reconciled; context-sync required",
                            "reconciled_from": historical_qa_pass.get("key") or "legacy",
                        }
                        return TransactionPlan(
                            candidate,
                            reconcile_event,
                            (transaction.mutation(self.paths.active_context, self._render_body(candidate, queue)),),
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
            try:
                resolved_kind = resolve_epic_kind(self.paths.project, epic_id, role=role)
            except Exception:
                resolved_kind = "feature"
            candidate = Cursor(
                epic_id=epic_id,
                role=role,
                kind=resolved_kind,
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

    def rewind(self, phase: str, *, reason: str = "manual rewind", step_id: str | None = None) -> Transition:
        target_phase = str(phase or "").strip().upper()
        if target_phase not in {
            "DECOMPOSE",
            "CREATIVE",
            "QA",
            "BUGFIX",
            "SECURITY",
        }:
            raise TransitionError(f"unsupported rewind phase: {phase!r}")

        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            queue = None if target_phase == "DECOMPOSE" else self._queue(current)
            candidate = self._copy_cursor(current)
            candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
            candidate.phase = target_phase
            if target_phase == "CREATIVE":
                if queue is None:
                    raise TransitionError("cannot rewind to CREATIVE without decompose index")
                creative_step = resolve_creative_step(self.paths.project, queue)
                if creative_step is None:
                    if not queue.pending:
                        raise TransitionError("cannot rewind to CREATIVE: no pending step")
                    creative_step = queue.pending[0]
                candidate.step_id = creative_step.step_id
            elif target_phase == "SECURITY":
                if queue is None:
                    raise TransitionError("cannot rewind to SECURITY without decompose index")
                wanted = str(step_id or "").strip() or None
                if wanted:
                    match = next((item for item in queue.steps if item.step_id == wanted), None)
                    if match is None:
                        raise TransitionError(f"cannot rewind to SECURITY: step {wanted!r} missing from index")
                    candidate.step_id = match.step_id
                elif queue.pending:
                    candidate.step_id = queue.pending[0].step_id
                else:
                    raise TransitionError("cannot rewind to SECURITY: no pending audit step")
            else:
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
                "phase": candidate.phase,
                "step_id": candidate.step_id,
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

    def finish(
        self,
        *,
        step_id: str | None = None,
        reason: str = "session completed",
        gate_pass: GateVerdict | None = None,
    ) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            finish_step = step_id
            if self._remap_obsolete_phase(current.phase) != current.phase:
                current = self._normalize_obsolete_cursor(current)
                if finish_step and finish_step in _OBSOLETE_PHASE_REMAP:
                    finish_step = current.step_id
            # Product QA FAIL + open bugfix queue must route even when Codex/runtime
            # never persisted verdict_recorded (no subagent-stop hook). Artifact SoT wins.
            if self._qa_failure_ready(current):
                pending_qa_failure = self._pending_qa_failure(transaction, current) or {}
                route_key = (
                    f"{current.phase_epoch}:{current.epic_id}:{current.step_id}:"
                    f"qa-failure-finish:{pending_qa_failure.get('key') or 'artifact'}"
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
                    "reconciled_from": pending_qa_failure.get("key") or "qa-artifact",
                    "route": "BUGFIX",
                }
                qa_gate_pass = GateVerdict(
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
                    step_id=finish_step,
                    reason="finish-reconcile:verify-qa:FAIL",
                    event=route_event,
                    gate_pass=qa_gate_pass,
                )
            return self._finish_plan(
                current,
                transaction,
                step_id=finish_step,
                reason=reason,
                event={"event": "finish"},
                gate_pass=gate_pass,
            )

        result = self.store.transact(planner)
        return self._transition_from_result(result, event=str(result.event.get("event") or "finish"), reason=str(result.event.get("reason") or reason))

    def accept_verdict(self, record: GateVerdict, *, source: str = "subagent-stop", expected_agent_id: str | None = None) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run start first")
            if self._remap_obsolete_phase(current.phase) != current.phase:
                current = self._normalize_obsolete_cursor(current)
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
            if record.agent_id not in _ENGINE_GATE_AGENTS:
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
            if record.agent_id == "verify-decompose" and record.verdict == "PASS":
                try:
                    validate_decompose_tree(
                        self.paths.project,
                        current.role,
                        current.epic_id,
                        require_fresh_pending=True,
                    )
                except (ValueError, FileNotFoundError, OSError) as exc:
                    raise TransitionError(
                        f"cannot accept verify-decompose PASS: invalid decompose tree — {exc}"
                    ) from exc
                event["gate_role"] = "decompose_complete"
                return self._finish_plan(
                    current,
                    transaction,
                    step_id=record.step_id,
                    reason=f"{source}:{record.agent_id}:PASS",
                    event=event,
                    gate_pass=record,
                )
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
                prior_fails = transaction.event_match_count(
                    "verdict_recorded",
                    {
                        "agent_id": record.agent_id,
                        "epic_id": current.epic_id,
                        "step_id": current.step_id,
                        "verdict": "FAIL",
                        "verdict_phase_epoch": current.phase_epoch,
                    },
                )
                repair_count = transaction.event_match_count(
                    "repair_recorded",
                    {
                        "phase": current.phase,
                        "step_id": current.step_id,
                    },
                )
                fail_cycles = prior_fails + 1
                if (
                    fail_cycles >= MAX_VERIFY_REPAIR_CYCLES
                    and repair_count >= MAX_VERIFY_REPAIR_CYCLES
                ):
                    restart_prefix = f"{current.epic_id}:{current.step_id}:"
                    restart_number = transaction.event_count("step_restarted", restart_prefix) + 1
                    reason = (
                        f"verify_repair_exhausted:{record.agent_id} "
                        f"fails={fail_cycles} repairs={repair_count}"
                    )
                    if restart_number > MAX_STEP_RESTARTS:
                        candidate = self._copy_cursor(current)
                        halt_reason = (
                            f"step_restart_exhausted:{current.step_id} after "
                            f"{MAX_STEP_RESTARTS} restarts ({reason})"
                        )
                        candidate.status = CursorStatus.HALTED
                        candidate.failure = self._failure(
                            "boundary",
                            "step_restart_exhausted",
                            halt_reason,
                            retryable=False,
                            attempt=candidate.attempt,
                            details={"agent_id": record.agent_id},
                        )
                        return TransactionPlan(
                            candidate,
                            {
                                "event": "halt",
                                "reason": halt_reason,
                                "phase": current.phase,
                                "step_id": current.step_id,
                            },
                            (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
                            (event,),
                        )
                    candidate = self._copy_cursor(current)
                    candidate.status = CursorStatus.ACTIVE
                    candidate.attempt = 0
                    candidate.failure = None
                    candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
                    candidate.phase_epoch += 1
                    restart_event = {
                        "event": "step_restarted",
                        "key": f"{restart_prefix}{restart_number}",
                        "reason": reason,
                        "phase": candidate.phase,
                        "step_id": candidate.step_id,
                        "epic_id": candidate.epic_id,
                        "restart": restart_number,
                        "session_id": candidate.session_id,
                        "phase_epoch": candidate.phase_epoch,
                        "details": {
                            "agent_id": record.agent_id,
                            "trigger": "verify_repair_exhausted",
                            "fail_cycles": fail_cycles,
                            "repair_count": repair_count,
                        },
                    }
                    return TransactionPlan(
                        candidate,
                        restart_event,
                        (
                            transaction.mutation(
                                self.paths.active_context,
                                self._render_restart_body(
                                    candidate, reason=reason, restart_number=restart_number
                                ),
                            ),
                        ),
                        (event,),
                    )
                return TransactionPlan(None, event)
            if (
                current.phase == "QA"
                and record.agent_id == "verify-qa"
                and self._qa_pass_ready(current)
            ):
                artifacts = phase_artifacts(self.paths.project, current.role, current.epic_id, "qa")
                previous = transaction.latest_event("verdict_accepted") or transaction.latest_event("finish")
                if artifacts and previous and previous.get("source_phase") == "BUGFIX":
                    baseline = str(previous.get("qa_artifact_digest") or "")
                    current_digest = file_digest(artifacts[-1]) or ""
                    if baseline and current_digest == baseline:
                        raise TransitionError("cannot accept QA PASS: qa_new_artifact_required")
                candidate = self._copy_cursor(current)
                candidate.status = CursorStatus.ACTIVE
                candidate.attempt = 0
                candidate.failure = None
                event["context_sync_required"] = True
                event["qa_artifact_digest"] = file_digest(artifacts[-1]) if artifacts else None
                event["qa_artifact_path"] = (
                    artifacts[-1].resolve().relative_to(self.paths.project.resolve()).as_posix()
                    if artifacts
                    else None
                )
                event["target_reason"] = "qa passed; context-sync required"
                return TransactionPlan(
                    candidate,
                    event,
                    (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
                )
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
            metadata={
                "key": result.event.get("key"),
                "agent_id": result.event.get("agent_id"),
                "verdict": result.event.get("verdict"),
                "context_sync_required": result.event.get("context_sync_required", False),
                "session_keep_alive": result.event.get("session_keep_alive", False),
            },
        )

    def complete_context_sync(
        self,
        record: ContextSyncResult,
        *,
        source: str = "subagent-stop",
    ) -> Transition:
        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cursor does not exist; run context sync from an active loop")
            key = f"{record.session_id}:{record.epic_id}:{record.sync_path}:{record.recorded_at}"
            for event_name in ("context_sync_completed", "context_sync_failed"):
                if transaction.event_seen(event_name, key):
                    return TransactionPlan(
                        current,
                        {"event": "context_sync_duplicate", "key": key},
                        changed=False,
                    )
            if current.phase != "QA" or current.step_id != "QA":
                raise TransitionError(
                    f"context-sync requires active QA phase: cursor={current.phase}/{current.step_id}"
                )
            if current.session_id != record.session_id:
                raise TransitionError("context-sync session mismatch")
            if current.epic_id != record.epic_id:
                raise TransitionError("context-sync epic mismatch")
            if self._qa_pass_event(transaction, current) is None:
                raise TransitionError("context-sync requires accepted verify-qa PASS")
            event = {
                "event": "context_sync_failed" if record.status == "fail" else "context_sync_completed",
                "key": key,
                "source": source,
                "agent_id": record.agent_id,
                "status": record.status,
                "session_id": record.session_id,
                "epic_id": record.epic_id,
                "step_id": current.step_id,
                "phase": current.phase,
                "phase_epoch": current.phase_epoch,
                "sync_path": record.sync_path,
                "recorded_at": record.recorded_at,
            }
            if record.status == "fail":
                return TransactionPlan(None, event)
            artifact = self._context_sync_path(current, record.sync_path)
            return self._finish_plan(
                current,
                transaction,
                step_id=current.step_id,
                reason=f"{source}:context-sync:done",
                event=event,
                context_sync_path=str(artifact),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(
            result,
            event=str(result.event.get("event") or "context_sync_completed"),
            reason=str(result.event.get("reason") or result.event.get("status") or "context-sync"),
            metadata={
                "agent_id": result.event.get("agent_id"),
                "status": result.event.get("status"),
                "sync_path": result.event.get("sync_path"),
            },
        )

    def reject_verdict(
        self,
        *,
        agent_id: str,
        diagnostic_codes: list[str] | tuple[str, ...],
        errors: list[str] | tuple[str, ...],
        source: str = "subagent-stop",
        max_retries: int = MAX_VERIFY_REPAIR_CYCLES - 1,
    ) -> tuple[int, str]:
        """Reject an invalid gate payload.

        Returns ``(retry_number, outcome)`` where outcome is ``continue``,
        ``restarted`` (step restarted after schema budget), or ``halted``.
        """

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
            # Schema budget exhausted → restart same step (not immediate halt).
            restart_prefix = f"{current.epic_id}:{current.step_id}:"
            restart_number = transaction.event_count("step_restarted", restart_prefix) + 1
            reason = f"schema_retry_exhausted:{agent_id}"
            if restart_number > MAX_STEP_RESTARTS:
                candidate = self._copy_cursor(current)
                halt_reason = f"step_restart_exhausted:{current.step_id} after {MAX_STEP_RESTARTS} restarts ({reason})"
                candidate.status = CursorStatus.HALTED
                candidate.failure = self._failure(
                    "boundary",
                    "step_restart_exhausted",
                    halt_reason,
                    retryable=False,
                    attempt=candidate.attempt,
                    details={"agent_id": agent_id},
                )
                halt = {"event": "halt", "reason": halt_reason, "phase": current.phase, "step_id": current.step_id}
                mutations = (transaction.mutation(self.paths.active_context, self._render_body(candidate)),)
                return TransactionPlan(candidate, halt, mutations, (rejection,))
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.ACTIVE
            candidate.attempt = 0
            candidate.failure = None
            candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
            candidate.phase_epoch += 1
            restart_event = {
                "event": "step_restarted",
                "key": f"{restart_prefix}{restart_number}",
                "reason": reason,
                "phase": candidate.phase,
                "step_id": candidate.step_id,
                "epic_id": candidate.epic_id,
                "restart": restart_number,
                "session_id": candidate.session_id,
                "phase_epoch": candidate.phase_epoch,
                "details": {"agent_id": agent_id, "trigger": "schema_retry_exhausted"},
            }
            mutations = (
                transaction.mutation(
                    self.paths.active_context,
                    self._render_restart_body(candidate, reason=reason, restart_number=restart_number),
                ),
            )
            return TransactionPlan(candidate, restart_event, mutations, (rejection,))

        result = self.store.transact(planner)
        event_name = str(result.event.get("event") or "")
        if event_name == "step_restarted":
            return max_retries + 1, "restarted"
        if event_name == "halt" or (result.cursor and result.cursor.status == CursorStatus.HALTED):
            return max_retries + 1, "halted"
        retry_number = int(result.event.get("retry") or 1)
        return retry_number, "continue"

    def record_event(self, event: dict[str, Any]) -> None:
        self.store.record_event(event)

    def retry(self, reason: str, *, expected_revision: int | None = None, details: dict[str, Any] | None = None) -> Transition:
        """Soft session retry: always mint a new session_id + phase_epoch.

        FORBIDDEN: re-run work under the same GATE_IDENTITY / session_id.
        Outer cli must rebuild the prompt from the new cursor and start a new runtime process.
        """

        def planner(current: Cursor | None, transaction: StoreTransaction) -> TransactionPlan:
            if current is None:
                raise TransitionError("cannot retry without cursor")
            if expected_revision is not None and current.revision != expected_revision:
                return TransactionPlan(current, {"event": "retry_skipped", "reason": "cursor advanced externally"}, changed=False)
            if current.status == CursorStatus.COMPLETE:
                raise TransitionError("cannot retry a complete cursor")
            if current.status == CursorStatus.HALTED:
                raise TransitionError("cannot retry a halted cursor")
            previous_session = current.session_id
            candidate = self._copy_cursor(current)
            candidate.status = CursorStatus.ACTIVE
            candidate.attempt += 1
            candidate.failure = None
            candidate.session_id = f"session-{uuid.uuid4().hex[:12]}"
            candidate.phase_epoch += 1
            return TransactionPlan(
                candidate,
                {
                    "event": "retry",
                    "reason": reason,
                    "phase": candidate.phase,
                    "step_id": candidate.step_id,
                    "attempt": candidate.attempt,
                    "session_id": candidate.session_id,
                    "previous_session_id": previous_session,
                    "phase_epoch": candidate.phase_epoch,
                    "details": details or {},
                },
                (transaction.mutation(self.paths.active_context, self._render_body(candidate)),),
            )

        result = self.store.transact(planner)
        return self._transition_from_result(
            result,
            event=str(result.event.get("event") or "retry"),
            reason=str(result.event.get("reason") or reason),
            metadata={
                "session_id": result.event.get("session_id"),
                "previous_session_id": result.event.get("previous_session_id"),
                "attempt": result.event.get("attempt"),
                "phase_epoch": result.event.get("phase_epoch"),
            },
        )

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
