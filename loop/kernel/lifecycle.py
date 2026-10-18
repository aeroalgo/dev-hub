from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import MAX_VERIFY_REPAIR_CYCLES, LoopEngine, TransitionError
from .implement_schema import flush_implement_for_verify, validate_implement_artifact
from .index import (
    decompose_yaml_problems,
    implement_path,
    load_queue,
    validate_decompose_tree,
)
from .inventory import (
    MANAGED_INVENTORY_AGENTS,
    inventory_schema_for_agent,
    write_inventory_sidecar,
)
from .store import LoopPaths
from .pre_emit import schema_reject_reason, verify_pre_emit_stamp
from .verdict import (
    MANAGED_GATE_AGENTS,
    MANAGED_REPAIR_AGENTS,
    SCHEMA_GATE_VERDICT,
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
                "GATE_IDENTITY identifies the live session for PARENT_EVIDENCE_ID only. "
                "Do NOT put session_id, epic_id, or step_id into the repair JSON fence.\n"
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
                "ANTI-THRASH (HARD): Read each BLOCKERS path first. If the requested token/selector/"
                "assert is already present, do NOT duplicate or 'strengthen' CSS. For computed-style / "
                "Playwright / 8px-vs-token mismatches when source is already correct: status=fail with "
                "remaining_blockers kept and reason runtime_not_source (sync/build/clear-cache) or "
                "focus_visible_mismatch — FORBIDDEN more cosmetic selectors or flipping "
                "--ds-radius-md <-> --ds-radius-sm. Contradictory BLOCKERS fix text -> "
                "status=fail prompt_incomplete:blocker_row, no product edits.\n"
                "The final response must contain exactly one fenced json object with ONLY these keys: "
                'schema: "loop-repair-result/v1", agent_id: "gate-repair", '
                f'parent_evidence_id: "{cursor.session_id}", status (done|partial|fail), '
                "fixed_blockers, remaining_blockers, recorded_at.\n"
                "FORBIDDEN fence keys: session_id, epic_id, step_id, blockers, changed_paths, "
                "verification, repair_status, evidence, evidence_sha256.\n"
                "Validate it with python3 $DEV_HUB/bin/loop.py validate --project "
                f"{self.paths.project} --schema loop-repair-result/v1 --payload '<json>'. "
                "Do NOT use validate-verdict for repair results.\n"
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
        if (
            agent_type == "verify-implement"
            and cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}
        ):
            # Machine-owned status write BEFORE verifier reads the artifact.
            # Agents must never invent status literals (passed/done/completed).
            queue = load_queue(self.paths.project, cursor.role, cursor.epic_id)
            step = next(
                (item for item in queue.steps if item.step_id == cursor.step_id),
                None,
            )
            if step is None:
                raise TransitionError(
                    f"implement-flush denied: step {cursor.step_id!r} missing from decompose index"
                )
            flush_implement_for_verify(
                implement_path(self.paths.project, queue.role, queue.epic_id, step),
                expected_step_id=cursor.step_id,
                expected_plan_id=queue.epic_id,
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
            "HARD PRE-EMIT (machine-enforced): before the final fence you MUST run "
            "python3 $DEV_HUB/bin/loop.py validate-verdict --project "
            f"{self.paths.project} --payload '<exact-final-json>' "
            "until valid:true. That command writes a pre-emit stamp and returns emit_exactly. "
            "SubagentStop DENIES any fence whose semantic fields (all keys except recorded_at) "
            "do not match the stamp. Copy emit_exactly into the final fence; recorded_at may "
            "differ. Changing verdict/ids/evidence_sha256 requires a new validate-verdict. "
            "Allowed keys only: schema,agent_id,verdict,step_id,session_id,epic_id,"
            "recorded_at,evidence_sha256(optional). Never require evidence_sha256. "
            "FORBIDDEN keys: evidence,blockers,touched_paths,"
            "evidence_id,reason,findings,gate,status,checkpoints. "
            "After the fence: zero tool calls."
        )
        return (
            f"agent_type={agent_type}\n{identity}\n"
            "Machine SoT: exactly one fenced `json` object with "
            '`schema: "loop-gate-verdict/v1"`, `agent_id`, `verdict` (PASS|FAIL|BLOCKED), '
            "step_id, session_id, epic_id, and recorded_at.\n"
            f"{validation}\n"
            "The boundary hook re-validates the fence and atomically advances the loop on PASS."
        )

    def _stop_repair(self, payload: dict[str, Any], cursor) -> HookAction:
        message = _message(payload)
        validation = validate_repair_message(message, session_id=cursor.session_id)
        if not validation.valid or validation.record is None:
            # Delayed gate-repair from a previous GATE_IDENTITY after session rotate /
            # step_restart must NOT exit-2 the live parent or ask to "re-emit" under the
            # new session_id (that launders stale repairs into the new identity).
            if "repair_wrong_parent_evidence_id" in validation.diagnostic_codes:
                self.engine.record_event(
                    {
                        "event": "stale_repair_ignored",
                        "agent_id": "gate-repair",
                        "phase": cursor.phase,
                        "step_id": cursor.step_id,
                        "session_id": cursor.session_id,
                        "diagnostic_codes": ["stale_repair_ignored", "repair_wrong_parent_evidence_id"],
                        "errors": list(validation.errors),
                    }
                )
                return HookAction(
                    True,
                    True,
                    reason="stale_repair_ignored:parent_evidence_id_mismatch",
                    diagnostic_codes=("stale_repair_ignored", "repair_wrong_parent_evidence_id"),
                )
            self.engine.record_event(
                {
                    "event": "repair_result_rejected",
                    "agent_id": "gate-repair",
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "session_id": cursor.session_id,
                    "epic_id": cursor.epic_id,
                    "diagnostic_codes": list(validation.diagnostic_codes),
                    "errors": list(validation.errors),
                }
            )
            allowed = (
                "schema,agent_id,parent_evidence_id,status,fixed_blockers,"
                "remaining_blockers,recorded_at"
            )
            reason = (
                "re-emit valid loop-repair-result/v1 JSON fence with ONLY allowed keys "
                f"({allowed}); FORBIDDEN: session_id,epic_id,step_id,blockers,"
                "changed_paths,verification,repair_status"
            )
            if "repair_invented_prompt_incomplete" in validation.diagnostic_codes:
                reason = (
                    "re-emit loop-repair-result/v1: set parent_evidence_id to GATE_IDENTITY "
                    "session_id and repair the concrete BLOCKERS; never use "
                    "prompt_incomplete:parent_evidence_id"
                )
            elif any(
                code.startswith("schema_") for code in validation.diagnostic_codes
            ):
                detail = " | ".join(str(err)[:120] for err in validation.errors[:3])
                reason = f"{reason}. last_errors={detail}"
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

    def _reject_verdict_action(
        self,
        *,
        agent_type: str,
        diagnostic_codes: tuple[str, ...] | list[str],
        errors: tuple[str, ...] | list[str],
        continue_reason: str | None = None,
    ) -> HookAction:
        retry_number, outcome = self.engine.reject_verdict(
            agent_id=agent_type,
            diagnostic_codes=diagnostic_codes,
            errors=errors,
        )
        codes = tuple(diagnostic_codes)
        if outcome == "halted":
            return HookAction(
                False,
                False,
                2,
                f"step_restart_exhausted:{agent_type}",
                codes + ("step_restart_exhausted",),
            )
        if outcome == "restarted":
            return HookAction(
                False,
                False,
                2,
                (
                    f"step_restarted:{agent_type} after {MAX_VERIFY_REPAIR_CYCLES} schema rejects — "
                    "same step restarts from scratch with new GATE_IDENTITY; "
                    "FORBIDDEN claim PASS/Готово; end session and let loop re-arm"
                ),
                codes + ("step_restarted",),
            )
        reason = continue_reason or (
            f"re-emit valid gate JSON (retry {retry_number}/{MAX_VERIFY_REPAIR_CYCLES - 1})"
        )
        if "{retry}" in reason:
            reason = reason.format(retry=retry_number, max=MAX_VERIFY_REPAIR_CYCLES - 1)
        return HookAction(False, False, 2, reason, codes)

    def _stop_inventory(self, payload: dict[str, Any], cursor, agent_type: str) -> HookAction:
        message = _message(payload)
        schema_id = inventory_schema_for_agent(agent_type) or "loop-sunset-inventory/v1"
        validation = validate_inventory_message(message, agent_id=agent_type)
        if not validation.valid or validation.record is None:
            return self._reject_verdict_action(
                agent_type=agent_type,
                diagnostic_codes=validation.diagnostic_codes,
                errors=validation.errors,
                continue_reason=f"re-emit valid {schema_id} JSON fence (retry {{retry}}/{{max}})",
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
        fence_payload, _ = extract_json_fence(message)

        def _stale_gate_ignored(reason: str, *, errors: list[str] | tuple[str, ...] = ()) -> HookAction:
            self.engine.record_event(
                {
                    "event": "stale_verdict_ignored",
                    "key": (
                        f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:"
                        f"{agent_type}:stale"
                    ),
                    "source": "subagent-stop",
                    "agent_id": agent_type,
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "session_id": cursor.session_id,
                    "diagnostic_codes": ["stale_verdict_ignored"],
                    "errors": [reason, *list(errors)],
                }
            )
            return HookAction(
                True,
                True,
                reason=f"stale_verdict_ignored:{reason}",
                diagnostic_codes=("stale_verdict_ignored",),
            )

        if not validation.valid or validation.record is None:
            # Foreign/old GATE_IDENTITY fence after rotate — do not burn schema-reject budget.
            if isinstance(fence_payload, dict):
                fence_session = str(fence_payload.get("session_id") or "").strip()
                if fence_session and fence_session != cursor.session_id:
                    return _stale_gate_ignored(
                        "session_mismatch_in_invalid_fence",
                        errors=validation.errors,
                    )
            retry_number, outcome = self.engine.reject_verdict(
                agent_id=agent_type,
                diagnostic_codes=validation.diagnostic_codes,
                errors=validation.errors,
            )
            if outcome == "halted":
                return HookAction(
                    False,
                    False,
                    2,
                    f"step_restart_exhausted:{agent_type}",
                    tuple(validation.diagnostic_codes) + ("step_restart_exhausted",),
                )
            if outcome == "restarted":
                return HookAction(
                    False,
                    False,
                    2,
                    (
                        f"step_restarted:{agent_type} after {MAX_VERIFY_REPAIR_CYCLES} schema rejects — "
                        "same step restarts from scratch with new GATE_IDENTITY; "
                        "FORBIDDEN claim PASS/Готово; end session and let loop re-arm"
                    ),
                    tuple(validation.diagnostic_codes) + ("step_restarted",),
                )
            reason = schema_reject_reason(
                schema_id=SCHEMA_GATE_VERDICT,
                retry_number=retry_number,
                max_retries=MAX_VERIFY_REPAIR_CYCLES - 1,
                diagnostic_codes=validation.diagnostic_codes,
                errors=validation.errors,
                payload=fence_payload if isinstance(fence_payload, dict) else None,
            )
            return HookAction(False, False, 2, reason, validation.diagnostic_codes)

        assert isinstance(fence_payload, dict)
        record = validation.record
        # Only session rotate makes a fence foreign. Step advance still goes through
        # accept_verdict so same-session duplicates stay idempotent (verdict_duplicate).
        if record.session_id != cursor.session_id:
            return _stale_gate_ignored(
                f"session_mismatch:cursor={cursor.session_id},received={record.session_id}"
            )

        # Coerce implement enum aliases (passed→done) BEFORE PASS/FAIL handling so
        # checkpoints_pending from synonym typos never becomes a gate-repair cycle.
        if (
            agent_type == "verify-implement"
            and cursor.phase in {"IMPLEMENT", "TASK", "REFACTOR"}
        ):
            try:
                queue = load_queue(self.paths.project, cursor.role, cursor.epic_id)
                step = next(
                    (item for item in queue.steps if item.step_id == cursor.step_id),
                    None,
                )
                if step is not None:
                    validate_implement_artifact(
                        implement_path(
                            self.paths.project, queue.role, queue.epic_id, step
                        ),
                        expected_step_id=cursor.step_id,
                        expected_plan_id=queue.epic_id,
                        rewrite=True,
                    )
            except (ValueError, FileNotFoundError, OSError) as exc:
                # Unrecoverable schema (not an alias) — reject any verdict; do not repair prose.
                reject_reason = (
                    "cannot accept verify-implement verdict: invalid implement artifact — "
                    f"{exc}"
                )
                self.engine.record_event(
                    {
                        "event": "verdict_transition_rejected",
                        "key": (
                            f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:"
                            f"{agent_type}:implement_schema"
                        ),
                        "source": "subagent-stop",
                        "agent_id": agent_type,
                        "phase": cursor.phase,
                        "step_id": cursor.step_id,
                        "diagnostic_codes": ["implement_schema_invalid"],
                        "errors": [str(exc)],
                    }
                )
                return HookAction(
                    False,
                    False,
                    2,
                    reject_reason,
                    ("implement_schema_invalid",),
                )

        stamp_ok, stamp_errors, stamp_codes = verify_pre_emit_stamp(self.paths, fence_payload)
        if not stamp_ok:
            retry_number, outcome = self.engine.reject_verdict(
                agent_id=agent_type,
                diagnostic_codes=stamp_codes,
                errors=stamp_errors,
            )
            if outcome == "halted":
                return HookAction(
                    False,
                    False,
                    2,
                    f"step_restart_exhausted:{agent_type}",
                    tuple(stamp_codes) + ("step_restart_exhausted",),
                )
            if outcome == "restarted":
                return HookAction(
                    False,
                    False,
                    2,
                    (
                        f"step_restarted:{agent_type} after {MAX_VERIFY_REPAIR_CYCLES} schema rejects — "
                        "same step restarts from scratch with new GATE_IDENTITY; "
                        "FORBIDDEN claim PASS/Готово; end session and let loop re-arm"
                    ),
                    tuple(stamp_codes) + ("step_restarted",),
                )
            reason = schema_reject_reason(
                schema_id=SCHEMA_GATE_VERDICT,
                retry_number=retry_number,
                max_retries=MAX_VERIFY_REPAIR_CYCLES - 1,
                diagnostic_codes=stamp_codes,
                errors=stamp_errors,
                payload=fence_payload,
            )
            return HookAction(False, False, 2, reason, stamp_codes)

        if (
            validation.record.verdict == "PASS"
            and agent_type == "verify-decompose"
            and cursor.phase == "DECOMPOSE"
        ):
            tree_error: str | None = None
            try:
                validate_decompose_tree(self.paths.project, cursor.role, cursor.epic_id)
            except (ValueError, FileNotFoundError, OSError) as exc:
                tree_error = str(exc)
            if tree_error is None:
                leftover = decompose_yaml_problems(self.paths.project, cursor.role, cursor.epic_id)
                if leftover:
                    tree_error = "; ".join(leftover[:5])
            if tree_error:
                reject_reason = (
                    f"cannot accept verify-decompose PASS: invalid decompose tree — {tree_error}"
                )
                self.engine.record_event(
                    {
                        "event": "verdict_transition_rejected",
                        "key": (
                            f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:"
                            f"{agent_type}:tree"
                        ),
                        "source": "subagent-stop",
                        "agent_id": agent_type,
                        "phase": cursor.phase,
                        "step_id": cursor.step_id,
                        "diagnostic_codes": ["decompose_tree_invalid"],
                        "errors": [tree_error],
                    }
                )
                return HookAction(
                    False,
                    False,
                    2,
                    reject_reason,
                    ("decompose_tree_invalid",),
                )

        try:
            transition = self.engine.accept_verdict(
                validation.record,
                expected_agent_id=agent_type,
            )
        except TransitionError as exc:
            message_text = str(exc)
            stale = (
                "session mismatch" in message_text
                or "step mismatch" in message_text
                or "epic mismatch" in message_text
            )
            if stale:
                # Child completed after session rotate / step advance — discard.
                # FORBIDDEN: exit-2 the live parent (triggers repair thrash on new identity).
                self.engine.record_event(
                    {
                        "event": "stale_verdict_ignored",
                        "key": (
                            f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:"
                            f"{agent_type}:stale"
                        ),
                        "source": "subagent-stop",
                        "agent_id": agent_type,
                        "phase": cursor.phase,
                        "step_id": cursor.step_id,
                        "session_id": cursor.session_id,
                        "diagnostic_codes": ["stale_verdict_ignored"],
                        "errors": [message_text],
                    }
                )
                return HookAction(
                    True,
                    True,
                    reason=f"stale_verdict_ignored:{message_text}",
                    diagnostic_codes=("stale_verdict_ignored",),
                )
            self.engine.record_event(
                {
                    "event": "verdict_transition_rejected",
                    "key": f"{cursor.session_id}:{cursor.epic_id}:{cursor.step_id}:{agent_type}:finish",
                    "source": "subagent-stop",
                    "agent_id": agent_type,
                    "phase": cursor.phase,
                    "step_id": cursor.step_id,
                    "diagnostic_codes": ["verdict_transition_rejected"],
                    "errors": [message_text],
                }
            )
            return HookAction(False, False, 2, message_text, ("verdict_transition_rejected",))
        except Exception as exc:
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
            return HookAction(
                False,
                False,
                2,
                f"cannot accept {agent_type} PASS: {exc}",
                ("verdict_transition_rejected",),
            )
        if transition.event == "step_restarted":
            return HookAction(
                False,
                False,
                2,
                (
                    f"step_restarted:{agent_type} after {MAX_VERIFY_REPAIR_CYCLES} verify+repair "
                    "cycles — same step restarts from scratch with new GATE_IDENTITY; "
                    "FORBIDDEN claim PASS/Готово; end session and let loop re-arm"
                ),
                ("step_restarted",),
                transition=_transition_dict(transition),
            )
        if transition.event == "halt" or transition.status.value == "halted":
            return HookAction(
                False,
                False,
                2,
                f"step_restart_exhausted:{agent_type}",
                ("step_restart_exhausted",),
                transition=_transition_dict(transition),
            )
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
