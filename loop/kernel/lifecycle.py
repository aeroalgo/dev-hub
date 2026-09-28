from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import LoopEngine, TransitionError
from .inventory import (
    MANAGED_INVENTORY_AGENTS,
    inventory_schema_for_agent,
    write_inventory_sidecar,
)
from .store import LoopPaths
from .verdict import (
    MANAGED_GATE_AGENTS,
    MANAGED_REPAIR_AGENTS,
    extract_json_fence,
    normalize_agent_id,
    validate_inventory_message,
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


def _is_managed_agent(agent_id: str) -> bool:
    return (
        agent_id in MANAGED_GATE_AGENTS
        or agent_id in MANAGED_REPAIR_AGENTS
        or agent_id in MANAGED_INVENTORY_AGENTS
    )


def _agent_type(payload: dict[str, Any], message: str, prompt: str = "") -> str:
    for source in (payload, payload.get("item"), payload.get("agent"), payload.get("subagent")):
        if not isinstance(source, dict):
            continue
        for key in ("agent_type", "subagent_type", "agent_id", "type", "name"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                normalized = normalize_agent_id(value)
                if _is_managed_agent(normalized):
                    return normalized
    match = _AGENT_RE.search(f"{message}\n{prompt}")
    if match:
        normalized = normalize_agent_id(match.group(1))
        if _is_managed_agent(normalized):
            return normalized
    candidate, _ = extract_json_fence(message)
    if isinstance(candidate, dict):
        normalized = normalize_agent_id(str(candidate.get("agent_id") or ""))
        if _is_managed_agent(normalized):
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
                f"PARENT_EVIDENCE_ID={cursor.session_id}\n"
                "Use the GATE_IDENTITY values verbatim and never derive them from a thread, epic, or directory.\n"
                "parent_evidence_id is a RESULT field only: copy PARENT_EVIDENCE_ID "
                f"({cursor.session_id}) into the JSON. It is never a missing parent prompt section.\n"
                "FORBIDDEN remaining_blockers: prompt_incomplete:parent_evidence_id and any "
                "prompt_incomplete for result-only fields (parent_evidence_id, recorded_at, agent_id, "
                "status, schema, fixed_blockers, remaining_blockers).\n"
                "Required parent sections already expected in the spawn prompt: BLOCKERS, ALLOW WRITE, VERIFY. "
                "If those product sections are absent, status=fail with "
                "prompt_incomplete:BLOCKERS|ALLOW WRITE|VERIFY and make no product edits.\n"
                "When BLOCKERS are present: apply the concrete ALLOW WRITE fixes, run the exact VERIFY "
                "command, then emit the result. Do not stop with empty fixed_blockers and invented "
                "protocol blockers.\n"
                "The final response must contain exactly one fenced json object with "
                'schema: "loop-repair-result/v1", agent_id: "gate-repair", '
                f'parent_evidence_id: "{cursor.session_id}", status (done|partial|fail), '
                "fixed_blockers, remaining_blockers, and recorded_at.\n"
                "Validate it with python3 $DEV_HUB/bin/loop.py validate-verdict --project "
                f"{self.paths.project} --payload '<json>'.\n"
                "Never spawn another agent and never call finish."
            )
        if agent_type in MANAGED_INVENTORY_AGENTS:
            schema_id = inventory_schema_for_agent(agent_type) or "loop-sunset-inventory/v1"
            return (
                f"agent_type={agent_type}\n{identity}\n"
                "You are a READ-ONLY inventory extraction agent. Never implement, never edit, never design.\n"
                "Required parent prompt sections for this agent: ALLOW READ / sunset_scope.\n"
                "If ALLOW READ is absent, return ok=false with diagnostic_codes including "
                "prompt_incomplete:ALLOW READ and emit an empty items list.\n"
                "The final response must contain exactly one fenced `json` object with "
                f'`schema: "{schema_id}"`, boundary_id, new_sot, forbidden_for_parent, '
                "diagnostic_codes, ok, and items[]. Each item must use mark REPLACE and "
                "Kind A|B|C|I; excerpt ≤ 40 lines; no design/how-to fields.\n"
                "Validate it with python3 $DEV_HUB/bin/loop.py validate-verdict --project "
                f"{self.paths.project} --payload '<json>'.\n"
                "Never spawn another agent and never call finish."
            )
        required_sections = {
            "verify-decompose": "ALLOW READ",
            "analyze-verify": "FINDINGS / COVERAGE / ALLOW READ",
            "verify-implement": "ALLOW READ",
            "verify-bugfix": "ALLOW READ",
            "verify-qa": "Suite results / ALLOW READ / Frozen QA checklist + checklist_sha256",
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
        validation = validate_repair_message(message, session_id=cursor.session_id)
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
            reason = "re-emit valid loop-repair-result/v1 JSON fence"
            if "repair_invented_prompt_incomplete" in validation.diagnostic_codes:
                reason = (
                    "re-emit loop-repair-result/v1: set parent_evidence_id to GATE_IDENTITY "
                    "session_id and repair the concrete BLOCKERS; never use "
                    "prompt_incomplete:parent_evidence_id"
                )
            elif "repair_wrong_parent_evidence_id" in validation.diagnostic_codes:
                reason = (
                    "re-emit loop-repair-result/v1 with parent_evidence_id equal to "
                    f"GATE_IDENTITY session_id ({cursor.session_id})"
                )
            return HookAction(
                False,
                False,
                2,
                reason,
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

    def _stop_inventory(self, payload: dict[str, Any], cursor, agent_type: str) -> HookAction:
        message = _message(payload)
        schema_id = inventory_schema_for_agent(agent_type) or "loop-sunset-inventory/v1"
        validation = validate_inventory_message(message, agent_id=agent_type)
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
                f"re-emit valid {schema_id} JSON fence (retry {retry_number}/2)",
                validation.diagnostic_codes,
            )
        try:
            report = write_inventory_sidecar(
                self.paths,
                agent_id=agent_type,
                session_id=cursor.session_id,
                payload=validation.record,
                step_id=cursor.step_id,
            )
        except Exception as exc:
            self.engine.record_event(
                {
                    "event": "inventory_sidecar_persist_failed",
                    "agent_id": agent_type,
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "report_schema": schema_id,
                    "diagnostic_codes": ["inventory_sidecar_persist_failed"],
                    "errors": [str(exc)],
                }
            )
            return HookAction(
                False,
                False,
                2,
                f"inventory_sidecar_persist_failed:{exc}",
                ("inventory_sidecar_persist_failed",),
            )
        item_count = len(getattr(report, "items", []) or [])
        ok = bool(getattr(report, "ok", True))
        self.engine.record_event(
            {
                "event": "inventory_recorded",
                "agent_id": agent_type,
                "phase": cursor.phase,
                "step_id": cursor.step_id,
                "report_schema": schema_id,
                "ok": ok,
                "item_count": item_count,
                "boundary_id": getattr(report, "boundary_id", None),
                "new_sot": getattr(report, "new_sot", None),
            }
        )
        return HookAction(
            True,
            True,
            reason=f"inventory_recorded:{agent_type}",
            transition={
                "event": "inventory_recorded",
                "phase": cursor.phase,
                "step_id": cursor.step_id,
                "status": cursor.status.value,
                "changed": True,
                "metadata": {
                    "agent_id": agent_type,
                    "report_schema": schema_id,
                    "ok": ok,
                    "item_count": item_count,
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
        if agent_type in MANAGED_INVENTORY_AGENTS:
            return self._stop_inventory(payload, cursor, agent_type)
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
