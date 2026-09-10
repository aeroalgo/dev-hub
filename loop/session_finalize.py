"""Shared session start identity + atomic close (Claude/Codex/DSH).

Session work identity is frozen at prepare_session. mb-finish may advance
armed_step mid-session; close artifacts must keep the start identity while
resume_from follows the post-finish cursor.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SESSION_START_IDENTITY_SCHEMA = "loop-session-start-identity/v1"
_PHASE_MODE_RE = re.compile(r"(?im)^\s*mode:\s*([^\s]+)")


@dataclass(frozen=True)
class SessionStartIdentity:
    schema: str = SESSION_START_IDENTITY_SCHEMA
    phase: str = ""
    step_id: str = ""
    epic_id: str = ""
    role: str = ""
    phase_run_id: str = ""
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, raw: Any) -> SessionStartIdentity | None:
        if not isinstance(raw, dict):
            return None
        return cls(
            schema=str(raw.get("schema") or SESSION_START_IDENTITY_SCHEMA),
            phase=str(raw.get("phase") or "").strip(),
            step_id=str(raw.get("step_id") or "").strip(),
            epic_id=str(raw.get("epic_id") or "").strip(),
            role=str(raw.get("role") or "").strip(),
            phase_run_id=str(raw.get("phase_run_id") or "").strip(),
            session_id=str(raw.get("session_id") or "").strip(),
        )


@dataclass(frozen=True)
class SessionCloseIdentity:
    """Identity used when committing terminal session artifacts."""

    record_phase: str
    record_step_id: str
    record_epic_id: str
    record_role: str
    resume_from: str
    session_id: str
    phase_run_id: str


def active_context_mode(text: str | None) -> str:
    if not text:
        return ""
    match = _PHASE_MODE_RE.search(text)
    return match.group(1).upper() if match else ""


def should_probe_analyze_promotion(
    *,
    armed_step: str | None,
    active_context_text: str | None = None,
    active_mode: str | None = None,
) -> bool:
    """Claude prepare_session rule: do not promote merely because cursor is ANALYZE.

    When armed_step and activeContext mode are both ANALYZE, a normal ANALYZE
    session must run until mb-finish analyze / bound receipt. Explicit finish
    moves the cursor off ANALYZE before IMPLEMENT promotion.
    """
    armed = str(armed_step or "").strip().upper()
    if armed != "ANALYZE":
        return True
    mode = str(active_mode or "").strip().upper() or active_context_mode(active_context_text)
    if mode == "ANALYZE":
        return False
    return True


def analyze_promotion_requires_bound_receipt(state: dict[str, Any]) -> bool:
    """True when ANALYZE already finished and promotion must validate receipt."""
    last_finished = str(state.get("last_finished_step") or "").strip().upper()
    if last_finished == "ANALYZE":
        return True
    finish = state.get("last_finish_tool")
    if not isinstance(finish, dict):
        return False
    name = str(finish.get("name") or "").strip().lower()
    step = str(finish.get("step_id") or "").strip().upper()
    return step == "ANALYZE" or name.endswith("analyze") or " mb-finish analyze" in f" {name}"


def ownership_expected_step(state: dict[str, Any]) -> str:
    """Gate fence ownership step for the current parent session.

    Prefer prepare-time session_start_identity.step_id. Mid-session
    mb-finish may advance armed_step (BUGFIX→QA); in-flight verify
    fences still belong to the frozen start step, not the post-finish cursor.
    """
    from loop.gate_identity import GateIdentity

    return GateIdentity.expected(state).step_id


def ownership_expected_epic(state: dict[str, Any]) -> str:
    from loop.gate_identity import GateIdentity

    return GateIdentity.expected(state).epic_id


def apply_ownership_identity(
    identity: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Overlay frozen session-start step/epic onto a projection gate identity."""
    from loop.gate_identity import GateIdentity

    sot = GateIdentity.expected(state)
    out = dict(identity or {})
    if sot.step_id:
        out["step"] = sot.step_id
    if sot.epic_id:
        out["epic_id"] = sot.epic_id
    return out

def post_finish_cursor_step(state: dict[str, Any]) -> str:
    """Live cursor after an in-session finish (resume target for next prepare)."""
    return str(
        state.get("armed_after_finish")
        or state.get("armed_step")
        or ""
    ).strip()


def freeze_session_start_identity(
    state: dict[str, Any],
    *,
    phase: str | None,
    step_id: str | None,
    session_id: str | None = None,
    phase_run_id: str | None = None,
) -> SessionStartIdentity:
    identity = SessionStartIdentity(
        phase=str(phase or state.get("loop_phase") or state.get("phase") or "").strip(),
        step_id=str(step_id or state.get("armed_step") or "").strip(),
        epic_id=str(state.get("armed_epic") or state.get("epic") or "").strip(),
        role=str(state.get("role") or state.get("armed_role") or "").strip(),
        phase_run_id=str(phase_run_id or state.get("phase_run_id") or "").strip(),
        session_id=str(session_id or state.get("session_id") or "").strip(),
    )
    state["session_start_identity"] = identity.to_dict()
    from loop.gate_identity import GateIdentity

    GateIdentity.bind_spawn_gate(state)
    return identity


def resolve_session_close_identity(
    state: dict[str, Any],
    *,
    fallback_step_id: str | None = None,
    fallback_phase: str | None = None,
    same_phase_retry: bool = False,
) -> SessionCloseIdentity:
    start = SessionStartIdentity.from_mapping(state.get("session_start_identity"))
    post_step = str(
        state.get("armed_after_finish")
        or state.get("armed_step")
        or fallback_step_id
        or ""
    ).strip()
    if start and start.step_id:
        record_step = start.step_id
    else:
        # No frozen prepare identity: follow live cursor (retryable sync / legacy).
        record_step = str(
            state.get("armed_step")
            or fallback_step_id
            or state.get("last_finished_step")
            or ""
        ).strip()
    if start and start.phase:
        record_phase = start.phase
    else:
        record_phase = str(
            state.get("loop_phase")
            or state.get("phase")
            or fallback_phase
            or record_step
            or ""
        ).strip()
    record_epic = str(
        (start.epic_id if start and start.epic_id else None)
        or state.get("armed_epic")
        or state.get("epic")
        or ""
    ).strip()
    record_role = str(
        (start.role if start and start.role else None)
        or state.get("role")
        or state.get("armed_role")
        or ""
    ).strip()
    session_id = str(
        (start.session_id if start and start.session_id else None)
        or state.get("session_id")
        or ""
    ).strip()
    phase_run_id = str(
        (start.phase_run_id if start and start.phase_run_id else None)
        or state.get("phase_run_id")
        or ""
    ).strip()
    # Repair-loop exhausted / retryable abort: outer loop must restart the
    # same phase+step — never resume on a prematurely promoted cursor.
    if same_phase_retry:
        resume_from = record_step
    else:
        resume_from = post_step or record_step
    return SessionCloseIdentity(
        record_phase=record_phase,
        record_step_id=record_step,
        record_epic_id=record_epic,
        record_role=record_role,
        resume_from=resume_from,
        session_id=session_id,
        phase_run_id=phase_run_id,
    )


def commit_session_close(
    cwd: Path | str,
    *,
    identity: SessionCloseIdentity,
    analysis: dict[str, Any],
    runtime_id: str,
    log_path: str | Path,
    exit_code: int,
    attempt: int,
    dirty: list[str],
    status: str,
    reason: str | None,
    abort_kind: str | None,
    retryable: bool | None,
    resume_dirty: bool,
    raw_session_log: str,
) -> Path:
    """Atomically-consistent close: events + trace + last-session share one identity."""
    from epic_paths import epic_dir as runtime_epic_dir
    from harness.hooks.session_resilience import write_last_session
    from loop.incidents.trace import append_trace
    from loop.runtime.session_events import append_session_events, parse_session_events

    cwd_p = Path(cwd)
    edir = runtime_epic_dir(cwd_p)
    append_session_events(
        edir,
        parse_session_events(raw_session_log, runtime_id),
        session_id=identity.session_id,
        step_id=identity.record_step_id,
        epic_id=identity.record_epic_id,
        role=identity.record_role,
        phase=identity.record_phase,
        outcome=analysis.get("outcome"),
    )
    append_trace(
        edir,
        identity.record_phase,
        session_id=identity.session_id,
        step_id=identity.record_step_id,
        epic_id=identity.record_epic_id,
        action="session_result",
        runtime_provider=runtime_id,
        detail={
            "runtime": runtime_id,
            "role": identity.record_role,
            "outcome": analysis.get("outcome"),
            "semantic_status": analysis.get("semantic_status"),
            "task_complete": analysis.get("task_complete"),
            "event_summary": analysis.get("event_summary") or {},
            "session_start_identity": {
                "phase": identity.record_phase,
                "step_id": identity.record_step_id,
                "epic_id": identity.record_epic_id,
                "phase_run_id": identity.phase_run_id,
            },
            "resume_from": identity.resume_from,
        },
    )
    return write_last_session(
        cwd_p,
        track="epic",
        status=status,
        reason=reason,
        plan_id=identity.record_epic_id,
        step_id=identity.record_step_id,
        resume_from=identity.resume_from,
        dirty=dirty,
        log_file=str(log_path),
        exit_code=exit_code,
        abort_kind=abort_kind,
        retryable=retryable,
        outcome=analysis.get("outcome"),
        retry_count=attempt,
        resume_dirty=resume_dirty,
        runtime=runtime_id,
        semantic_status=analysis.get("semantic_status"),
        task_complete=analysis.get("task_complete"),
        event_summary=analysis.get("event_summary"),
        role=identity.record_role,
        phase=identity.record_phase,
        first_action_taken=analysis.get("first_action_taken"),
        first_action_at=analysis.get("first_action_at"),
    )
