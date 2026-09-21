from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import LoopEngine, TransitionError
from .store import LoopPaths
from .verdict import (
    MANAGED_GATE_AGENTS,
    MANAGED_REPAIR_AGENTS,
    extract_json_fence,
    normalize_agent_id,
    validate_repair_message,
    validate_message,
)


_AGENT_RE = re.compile(r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)")


@dataclass(frozen=True)
class HookAction:
    ok: bool
    continue_session: bool
    exit_code: int = 0
    reason: str = ""
    diagnostic_codes: tuple[str, ...] = ()
    transition: dict[str, Any] | None = None

    def as_hook_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "continue": self.continue_session,
            "ok": self.ok,
        }
        if self.reason:
            payload["reason"] = self.reason
        if self.diagnostic_codes:
            payload["diagnostic_codes"] = list(self.diagnostic_codes)
        if self.transition is not None:
            payload["transition"] = self.transition
        return payload


def _message(payload: dict[str, Any]) -> str:
    for source in (payload, payload.get("item"), payload.get("agent"), payload.get("subagent")):
        if not isinstance(source, dict):
            continue
        for key in ("last_assistant_message", "message", "output", "last_message", "result"):
            value = source.get(key)
            if isinstance(value, dict):
                value = value.get("text") or value.get("message") or value.get("content")
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _prompt(payload: dict[str, Any]) -> str:
    for source in (payload, payload.get("item"), payload.get("agent"), payload.get("subagent")):
        if not isinstance(source, dict):
            continue
        for key in ("prompt", "input", "task"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _agent_type(payload: dict[str, Any], message: str, prompt: str = "") -> str:
    for source in (payload, payload.get("item"), payload.get("agent"), payload.get("subagent")):
        if not isinstance(source, dict):
            continue
        for key in ("agent_type", "subagent_type", "agent_id", "type", "name"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                normalized = normalize_agent_id(value)
                if normalized in MANAGED_GATE_AGENTS or normalized in MANAGED_REPAIR_AGENTS:
                    return normalized
    match = _AGENT_RE.search(f"{message}\n{prompt}")
    if match:
        normalized = normalize_agent_id(match.group(1))
        if normalized in MANAGED_GATE_AGENTS or normalized in MANAGED_REPAIR_AGENTS:
            return normalized
    candidate, _ = extract_json_fence(message)
    if isinstance(candidate, dict):
        normalized = normalize_agent_id(str(candidate.get("agent_id") or ""))
        if normalized in MANAGED_GATE_AGENTS or normalized in MANAGED_REPAIR_AGENTS:
            return normalized
    return ""


def _transition_dict(transition: Any) -> dict[str, Any]:
    return {
        "event": transition.event,
        "reason": transition.reason,
        "phase": transition.phase,
        "step_id": transition.step_id,
        "status": transition.status.value,
        "attempt": transition.attempt,
        "changed": transition.changed,
        "metadata": transition.metadata,
    }


class SubagentLifecycle:
    def __init__(self, paths: LoopPaths):
        self.paths = paths
        self.engine = LoopEngine(paths)

    def start_context(self, payload: dict[str, Any]) -> str | None:
        cursor = self.engine.store.read()
        if cursor is None or cursor.status.value in {"halted", "complete"}:
            return None
        agent_type = _agent_type(payload, _message(payload), _prompt(payload))
        if not agent_type:
            return None
        identity = (
            f"GATE_IDENTITY session_id={cursor.session_id} "
            f"epic_id={cursor.epic_id} step_id={cursor.step_id}"
        )
        if agent_type == "gate-repair":
            return (
                f"agent_type={agent_type}\n{identity}\n"
                "Use the GATE_IDENTITY values verbatim and never derive them from a thread, epic, or directory.\n"
                "The final response must contain exactly one fenced json object with "
                'schema: "loop-repair-result/v1", agent_id: "gate-repair", '
                "parent_evidence_id, status (done|partial|fail), "
                "fixed_blockers, remaining_blockers, and recorded_at.\n"
                "Validate it with python3 $DEV_HUB/bin/loop.py validate-verdict --project "
                f"{self.paths.project} --payload '<json>'.\n"
                "Repair only the concrete BLOCKERS paths in ALLOW WRITE, run the exact VERIFY command, "
                "never spawn another agent, and never call finish."
            )
        required_sections = {
            "verify-decompose": "ALLOW READ",
            "analyze-verify": "FINDINGS / COVERAGE / ALLOW READ",
            "verify-implement": "ALLOW READ",
            "verify-bugfix": "ALLOW READ",
            "verify-qa": "Suite results / ALLOW READ",
        }.get(agent_type, "ALLOW READ")
        validation = (
            f"Required parent prompt sections for this agent: {required_sections}. "
            "If any required section is absent, return FAIL with prompt_incomplete:<section> "
            "and do not invent product blockers.\n"
            "Before the final response, validate the exact JSON payload with: "
            "python3 $DEV_HUB/bin/loop.py validate-verdict --project "
            f"{self.paths.project} --payload '<json>'"
        )
        return (
            f"agent_type={agent_type}\n{identity}\n"
            "The final response must contain exactly one fenced `json` object with "
            '`schema: "loop-gate-verdict/v1"`, `agent_id`, `verdict` (PASS|FAIL|BLOCKED), '
            "step_id, session_id, epic_id, and recorded_at.\n"
            f"{validation}\n"
            "The boundary hook validates this response and atomically advances the loop on PASS."
        )

    def _stop_repair(self, payload: dict[str, Any], cursor) -> HookAction:
        message = _message(payload)
        validation = validate_repair_message(message)
        if not validation.valid or validation.record is None:
            self.engine.record_event(
                {
                    "event": "repair_result_rejected",
                    "agent_id": "gate-repair",
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "diagnostic_codes": list(validation.diagnostic_codes),
                    "errors": list(validation.errors),
                }
            )
            return HookAction(
                False,
                False,
                2,
                "re-emit valid loop-repair-result/v1 JSON fence",
                validation.diagnostic_codes,
            )
        record = validation.record
        self.engine.record_event(
            {
                "event": "repair_recorded",
                "agent_id": "gate-repair",
                "phase": cursor.phase,
                "step_id": cursor.step_id,
                "parent_evidence_id": record.parent_evidence_id,
                "status": record.status,
                "fixed_blockers": list(record.fixed_blockers),
                "remaining_blockers": list(record.remaining_blockers),
                "recorded_at": record.recorded_at,
            }
        )
        return HookAction(
            True,
            True,
            reason=f"repair_recorded:{record.status}",
            transition={
                "event": "repair_recorded",
                "phase": cursor.phase,
                "step_id": cursor.step_id,
                "status": cursor.status.value,
                "changed": True,
                "metadata": {
                    "agent_id": "gate-repair",
                    "repair_status": record.status,
                    "fixed_blockers": list(record.fixed_blockers),
                    "remaining_blockers": list(record.remaining_blockers),
                },
            },
        )

    def stop(self, payload: dict[str, Any]) -> HookAction:
        message = _message(payload)
        agent_type = _agent_type(payload, message, _prompt(payload))
        if not agent_type:
            return HookAction(True, True, reason="non_gate_subagent")

        cursor = self.engine.store.read()
        if cursor is None:
            return HookAction(False, False, 2, "cursor_missing", ("cursor_missing",))
        if agent_type == "gate-repair":
            return self._stop_repair(payload, cursor)
        # Parse the wire contract first.  Boundary identity is checked by the
        # locked engine so a delayed duplicate from a child that already
        # advanced the cursor is treated as idempotent, not as a fresh retry.
        validation = validate_message(message)
        if not validation.valid or validation.record is None:
            retry_number, halted = self.engine.reject_verdict(
                agent_id=agent_type,
                diagnostic_codes=validation.diagnostic_codes,
                errors=validation.errors,
            )
            if halted:
                return HookAction(
                    False,
                    False,
                    2,
                    f"schema_retry_exhausted:{agent_type}",
                    validation.diagnostic_codes,
                )
            return HookAction(
                False,
                False,
                2,
                f"re-emit valid loop-gate-verdict/v1 JSON fence (retry {retry_number}/2)",
                validation.diagnostic_codes,
            )

        try:
            transition = self.engine.accept_verdict(
                validation.record,
                expected_agent_id=agent_type,
            )
        except TransitionError as exc:
            self.engine.record_event(
                {
                    "event": "verdict_transition_rejected",
                    "key": f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:{agent_type}:finish",
                    "source": "subagent-stop",
                    "agent_id": agent_type,
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "diagnostic_codes": ["verdict_transition_rejected"],
                    "errors": [str(exc)],
                }
            )
            return HookAction(False, False, 2, str(exc), ("verdict_transition_rejected",))
        return HookAction(
            True,
            True,
            reason=transition.reason,
            transition=_transition_dict(transition),
        )


def load_payload() -> dict[str, Any]:
    import sys

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def paths_from_payload(payload: dict[str, Any]) -> LoopPaths:
    project = payload.get("cwd") or payload.get("project")
    return LoopPaths.for_project(project)


__all__ = ["HookAction", "SubagentLifecycle", "load_payload", "paths_from_payload"]
