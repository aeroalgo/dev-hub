from __future__ import annotations

import uuid
from typing import Any

from .index import Queue, load_queue, phase_artifacts, qa_verdict, update_step_status
from .model import Cursor, CursorStatus, Transition
from .store import CursorStore, LoopPaths, cursor_lock


class TransitionError(RuntimeError):
    pass


class LoopEngine:
    """One deterministic state machine with one mutable cursor."""

    def __init__(self, paths: LoopPaths):
        self.paths = paths
        self.store = CursorStore(paths)

    def _queue(self, cursor: Cursor) -> Queue:
        return load_queue(self.paths.project, cursor.role, cursor.epic_id)

    def _phase_after_queue(self, queue: Queue) -> tuple[str, str]:
        audit = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "audit")
        qa = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
        bugfix = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "bugfix")
        if not audit:
            return "AUDIT", "audit artifact required"
        if not qa:
            return "QA", "qa artifact required"
        verdict = qa_verdict(qa[-1])
        if verdict in {"fail", "failed", "blocked"}:
            if bugfix:
                return "QA", "bugfix exists; re-qa required"
            return "BUGFIX", "qa failed"
        if verdict in {"pass", "passed", "complete", "completed"}:
            return "DONE", "qa passed"
        return "QA", "qa verdict missing"

    def _target(self, cursor: Cursor) -> tuple[str, str, str]:
        queue = self._queue(cursor)
        if queue.pending:
            step = queue.pending[0]
            return "IMPLEMENT", step.step_id, f"pending step {step.step_id}"
        phase, reason = self._phase_after_queue(queue)
        return phase, phase, reason

    def start(self, epic_id: str, role: str = "back") -> Cursor:
        with cursor_lock(self.paths):
            existing = self.store.read()
            if existing and existing.status in {CursorStatus.ACTIVE, CursorStatus.RETRY}:
                if existing.epic_id != epic_id or existing.role != role:
                    raise TransitionError("cursor already owns another epic; finish or halt it first")
                return existing
            cursor = Cursor(
                epic_id=epic_id,
                role=role,
                phase="",
                step_id="",
                session_id=f"session-{uuid.uuid4().hex[:12]}",
            )
            phase, step, reason = self._target(cursor)
            cursor.phase, cursor.step_id = phase, step
            cursor.status = CursorStatus.COMPLETE if phase == "DONE" else CursorStatus.ACTIVE
            cursor.last_error = None
            self.store.write(cursor)
            self.store.append_event({"event": "start", "epic_id": epic_id, "role": role, "phase": phase, "step_id": step, "reason": reason})
            self._render(cursor)
            return cursor

    def finish(self, *, step_id: str | None = None, reason: str = "session completed") -> Transition:
        with cursor_lock(self.paths):
            cursor = self.store.read()
            if cursor is None:
                raise TransitionError("cursor does not exist; run start first")
            if cursor.status == CursorStatus.COMPLETE:
                return Transition("finish", "already complete", cursor.phase, cursor.step_id, cursor.status, cursor.attempt, changed=False)
            if cursor.status == CursorStatus.HALTED:
                raise TransitionError("cannot finish a halted cursor")
            if step_id and step_id != cursor.step_id:
                raise TransitionError(f"finish step mismatch: cursor={cursor.step_id}, received={step_id}")
            queue = self._queue(cursor)
            if cursor.phase == "IMPLEMENT":
                update_step_status(queue, cursor.step_id, "completed")
            elif cursor.phase == "AUDIT":
                if not phase_artifacts(self.paths.project, queue.role, queue.epic_id, "audit"):
                    raise TransitionError("cannot finish AUDIT without an audit artifact")
            elif cursor.phase == "QA":
                artifacts = phase_artifacts(self.paths.project, queue.role, queue.epic_id, "qa")
                verdict = qa_verdict(artifacts[-1]) if artifacts else None
                if verdict not in {"fail", "failed", "blocked", "pass", "passed", "complete", "completed"}:
                    raise TransitionError("cannot finish QA without a valid verdict")
            elif cursor.phase == "BUGFIX":
                if not phase_artifacts(self.paths.project, queue.role, queue.epic_id, "bugfix"):
                    raise TransitionError("cannot finish BUGFIX without a bugfix artifact")
            phase, next_step, target_reason = self._target(cursor)
            cursor.phase, cursor.step_id = phase, next_step
            cursor.status = CursorStatus.COMPLETE if phase == "DONE" else CursorStatus.ACTIVE
            cursor.attempt = 0
            cursor.last_error = None
            self.store.write(cursor)
            self.store.append_event({"event": "finish", "reason": reason, "phase": phase, "step_id": next_step, "target_reason": target_reason})
            self._render(cursor)
            return Transition("finish", reason, phase, next_step, cursor.status, cursor.attempt)

    def retry(self, reason: str) -> Transition:
        with cursor_lock(self.paths):
            cursor = self.store.read()
            if cursor is None:
                raise TransitionError("cannot retry without cursor")
            if cursor.status == CursorStatus.COMPLETE:
                raise TransitionError("cannot retry a complete cursor")
            if cursor.status == CursorStatus.HALTED:
                raise TransitionError("cannot retry a halted cursor")
            cursor.status = CursorStatus.RETRY
            cursor.attempt += 1
            cursor.last_error = reason
            self.store.write(cursor)
            self.store.append_event({"event": "retry", "reason": reason, "phase": cursor.phase, "step_id": cursor.step_id, "attempt": cursor.attempt})
            return Transition("retry", reason, cursor.phase, cursor.step_id, cursor.status, cursor.attempt)

    def halt(self, reason: str) -> Transition:
        with cursor_lock(self.paths):
            cursor = self.store.read()
            if cursor is None:
                raise TransitionError("cannot halt without cursor")
            cursor.status = CursorStatus.HALTED
            cursor.last_error = reason
            self.store.write(cursor)
            self.store.append_event({"event": "halt", "reason": reason, "phase": cursor.phase, "step_id": cursor.step_id})
            return Transition("halt", reason, cursor.phase, cursor.step_id, cursor.status, cursor.attempt)

    def status(self) -> dict[str, Any]:
        cursor = self.store.read()
        if cursor is None:
            return {"ok": True, "status": "uninitialized", "cursor": None, "cursor_path": str(self.paths.cursor)}
        return {"ok": True, "status": cursor.status.value, "cursor": cursor.to_dict(), "cursor_path": str(self.paths.cursor)}

    def doctor(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ok": True, "cursor_path": str(self.paths.cursor), "active_context": str(self.paths.active_context)}
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

    def _render(self, cursor: Cursor) -> None:
        queue = self._queue(cursor)
        lines = [
            "---",
            "schema: loop-generated-context/v1",
            f"role: {cursor.role.upper()}",
            f"mode: {cursor.phase}",
            f"epic_id: {cursor.epic_id}",
            f"step_id: {cursor.step_id}",
            "generated: true",
            "---",
            "",
            "## load_now",
            f"1. {queue.path.relative_to(self.paths.project).as_posix()} — queue/status",
        ]
        if cursor.phase == "IMPLEMENT" and cursor.step_id:
            step = next((item for item in queue.steps if item.step_id == cursor.step_id), None)
            if step and step.shard:
                lines.append(f"2. {step.shard} — current step artifact")
        lines.extend(
            [
                "",
                f"## Handoff {cursor.phase}",
                f"- Current cursor: `{cursor.epic_id}/{cursor.phase}/{cursor.step_id}`.",
                "- This file is generated by loop/kernel; do not edit it as state.",
                f"- Finish with: `bin/loop finish --step {cursor.step_id}`.",
            ]
        )
        self.store.write_active_context("\n".join(lines) + "\n")
