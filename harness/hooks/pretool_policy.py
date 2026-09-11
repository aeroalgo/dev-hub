#!/usr/bin/env python3
"""Pure policy adapters for PreToolUse lifecycle event dispatch.

Contains adapters for:
- ProjectBoundaryAdapter: blocks filesystem/command access outside project root.
- FinishBoundaryAdapter: blocks all tool execution after successful mb-finish.
- AgentPolicyAdapter: manages agent/task spawn parameters, model routing, identity, and context ledger read.
- BashPolicyAdapter: prevents runner-owned CLI, state overwrite, and out-of-scope search.
- WritePolicyAdapter: prevents state overwrite, immutable artifact mutation, and tracks context ledger write invalidation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_HOOKS_DIR = Path(__file__).resolve().parent
_HUB_ROOT = _HOOKS_DIR.parents[1]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

try:
    from hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PreToolUse,
        dispatch_pretool,
    )
except ImportError:
    from harness.hooks.hook_dispatch import (
        DecisionEnvelope,
        DiagnosticCode,
        DispatchBranch,
        EventContext,
        PreToolUse,
        dispatch_pretool,
    )

from _lib import (
    CUSTOM_OVERLAY,
    GATE_AGENTS,
    active_context_write_deny_reason,
    agent_enabled,
    bash_active_context_write_deny_reason,
    bash_discard_dirty_deny_reason,
    bash_gate_state_write_deny_reason,
    bash_project_boundary_deny_reason,
    current_gate_identity,
    gate_session_id,
    gate_state_write_deny_reason,
    is_epic_loop_env,
    last_verdict_allows_repair,
    load_state,
    mark_in_flight,
    normalize_type,
    product_cwd,
    project_boundary_deny_reason,
    recorded_artifact_write_deny_reason,
    resolve_hook_agent_type,
    resolved_spawn_model,
    runner_cli_deny_reason,
    save_state,
    sync_gate_identity,
    verify_step_path_violations,
    workflow_state_active,
    _discover_registry,
)
from context_ledger_adapters import (
    READ_TOOL_ALIASES,
    WRITE_TOOL_ALIASES,
    evaluate_read_payload,
    evaluate_write_payload,
)
from context_scope import ScopeResolver, is_search_command_line


_SPAWN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "Agent",
        "Task",
        "spawn_agent",
        "multi_agent_v1_spawn_agent",
        "multi_agent_v1.spawn_agent",
    }
)

BASH_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "Bash",
        "bash",
        "shell",
        "shell_command",
        "local_shell",
        "exec_command",
    }
)


def _is_spawn_tool(tool_name: str) -> bool:
    name = str(tool_name or "").strip()
    if name in _SPAWN_TOOL_NAMES:
        return True
    lower = name.lower().replace("-", "_")
    return lower.endswith("spawn_agent") or lower in {
        "agent",
        "task",
        "spawn_agent",
    }


def _load_epic_state(cwd: Path) -> dict[str, Any]:
    try:
        from harness.hooks.epic.core import load_epic_state

        state = load_epic_state(cwd)
        return state if isinstance(state, dict) else {}
    except (ImportError, OSError, TypeError, ValueError):
        pass
    try:
        from epic.core import load_epic_state

        state = load_epic_state(cwd)
        return state if isinstance(state, dict) else {}
    except (ImportError, OSError, TypeError, ValueError):
        pass
    try:
        from epic_lib import load_epic_state

        state = load_epic_state(cwd)
        return state if isinstance(state, dict) else {}
    except (ImportError, OSError, TypeError, ValueError):
        return {}


def finish_boundary_reason(cwd: str | Path) -> str | None:
    state = _load_epic_state(product_cwd(cwd))
    finish = state.get("last_finish_tool")
    if not isinstance(finish, dict):
        return None
    name = str(finish.get("name") or "")
    current_run = str(state.get("phase_run_id") or "").strip()
    finish_run = str(finish.get("phase_run_id") or "").strip()
    if not name.startswith("mb-finish ") or not current_run or current_run != finish_run:
        return None
    return (
        f"finish_boundary: {name} успешно завершён в текущем phase_run_id; "
        "немедленно останови текущий turn. Следующий runner-эпизод продолжит работу."
    )


# ============================================================================
# Policy Adapters
# ============================================================================

class ProjectBoundaryAdapter:
    """Validates that tool execution remains inside the project root."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        cwd = product_cwd(context.cwd)
        tool_name = str(context.tool_name or "").strip()
        tool_input = context.tool_input or {}

        if tool_name in BASH_TOOL_NAMES:
            cmd = str(tool_input.get("command") or "")
            reason = bash_project_boundary_deny_reason(cwd, cmd)
            if reason:
                return DecisionEnvelope.deny(
                    reason,
                    diagnostic_code=DiagnosticCode.PROJECT_BOUNDARY_DENY,
                    metadata={
                        "additional_context": "project-boundary DENY: доступ вне project root запрещён.",
                        "permissionDecisionReason": reason,
                    },
                )
            return None

        if tool_name in {"Read", "Edit", "Write", "NotebookEdit", "Glob", "Grep", "apply_patch"} or (
            tool_name in READ_TOOL_ALIASES or tool_name in WRITE_TOOL_ALIASES
        ):
            raw_path = (
                tool_input.get("file_path")
                or tool_input.get("notebook_path")
                or tool_input.get("path")
            )
            reason = project_boundary_deny_reason(cwd, raw_path, operation=tool_name.lower())
            if reason:
                return DecisionEnvelope.deny(
                    reason,
                    diagnostic_code=DiagnosticCode.PROJECT_BOUNDARY_DENY,
                    metadata={
                        "additional_context": "project-boundary DENY: доступ вне project root запрещён.",
                        "permissionDecisionReason": reason,
                    },
                )
            return None

        return None


class FinishBoundaryAdapter:
    """Enforces turn stoppage after mb-finish in the active phase run."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        if not is_epic_loop_env():
            return None

        cwd = product_cwd(context.cwd)
        reason = finish_boundary_reason(cwd)
        if reason:
            return DecisionEnvelope.deny(
                reason,
                diagnostic_code=DiagnosticCode.FINISH_BOUNDARY_DENY,
                metadata={
                    "additional_context": (
                        "finish-boundary DENY: mb-finish уже успешен. "
                        "Не вызывай другие tools; заверши текущий turn."
                    ),
                    "permissionDecisionReason": reason,
                },
            )
        return None


class AgentPolicyAdapter:
    """Enforces subagent contract validation, model routing, identity sync, and context read."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        tool_name = str(context.tool_name or "").strip()
        cwd = product_cwd(context.cwd)
        payload = dict(context.raw_payload or {})
        if not payload:
            payload = {
                "tool_name": tool_name,
                "tool_input": dict(context.tool_input or {}),
                "cwd": str(cwd),
                "session_id": context.session_id,
            }

        # 1. Handle Read/read tool aliases through ContextLedger
        if tool_name in READ_TOOL_ALIASES:
            receipt, resp = evaluate_read_payload(payload, provider="claude", cwd=str(cwd))
            out_meta = resp.get("hookSpecificOutput", {})
            if receipt.decision in ("duplicate", "denied"):
                reason = out_meta.get("permissionDecisionReason") or receipt.diagnostic or receipt.reason_code or "read_denied"
                return DecisionEnvelope.deny(
                    reason,
                    diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY,
                    metadata=out_meta,
                )
            return DecisionEnvelope.allow(
                reason="context_ledger_read_allowed",
                metadata=out_meta,
            )

        # 2. Check if this is an Agent/Task spawn tool
        if not _is_spawn_tool(tool_name):
            return None

        tool_input = dict(context.tool_input or {})
        if not tool_input.get("prompt") and isinstance(payload.get("prompt"), str):
            tool_input["prompt"] = payload["prompt"]

        raw_type = tool_input.get("subagent_type") or tool_input.get("agent_type")
        norm = normalize_type(raw_type)
        if _is_spawn_tool(tool_name) and tool_name not in {"Agent", "Task"} and not norm:
            norm = resolve_hook_agent_type({**payload, "tool_input": tool_input})
        if norm:
            tool_input["subagent_type"] = norm

        session_id = gate_session_id(payload)
        st = load_state(session_id, str(cwd))

        if not workflow_state_active(st, str(cwd) or None):
            return DecisionEnvelope.allow(updated_input=tool_input)

        sot_identity = current_gate_identity(str(cwd), session_id)
        sot_sess = str((sot_identity or {}).get("session_id") or "").strip()
        sot_epic = str((sot_identity or {}).get("epic_id") or "").strip()
        if sot_sess and sot_epic:
            try:
                from loop.gate_identity import GateIdentity

                GateIdentity.bind_spawn_gate(st, sot_identity)
            except ImportError:
                sync_gate_identity(st, sot_identity)
        elif not str((st.get("gate_identity") or {}).get("epic_id") or "").strip():
            # Keep incomplete projection out of state; spawn_validate will DENY.
            pass

        if session_id and not st.get("session_id"):
            st["session_id"] = session_id

        from spawn_validate import validate_spawn_input

        deny_reasons, notes = validate_spawn_input(tool_input, st, str(cwd) or None)
        norm = normalize_type(tool_input.get("subagent_type") or tool_input.get("agent_type"))
        definition = _discover_registry(str(cwd) or None).get(norm) if norm else None
        managed = bool(definition is not None and definition.managed)

        from epic.core import load_epic_state
        from loop.epic_transition import get_verify_agent

        epic = load_epic_state(str(cwd)) if cwd else {}
        current_phase = epic.get("phase") or st.get("mode") or ""
        expected_verify_agent = get_verify_agent(str(current_phase)) if current_phase else None
        if norm and expected_verify_agent and norm.startswith("verify") and norm != expected_verify_agent:
            notes.append(
                f"mismatched_verify_agent: phase '{current_phase}' expects '{expected_verify_agent}', got '{norm}'"
            )

        if norm and (managed or norm in GATE_AGENTS or norm in CUSTOM_OVERLAY):
            agent_file = Path(cwd or ".").resolve() / ".claude" / "agents" / f"{norm}.md"
            if not agent_file.is_file():
                agent_file = Path(cwd or ".").resolve() / "harness" / "agents" / f"{norm}.md"
            if not agent_file.is_file():
                agent_file = _HOOKS_DIR.parent / "agents" / f"{norm}.md"
            if not agent_file.is_file():
                deny_reasons.append(f"agent_file_missing: .claude/agents/{norm}.md не существует")

        spawn_model = resolved_spawn_model(tool_input, definition)
        prompt = tool_input.get("prompt") or ""

        if norm == "gate-repair":
            if not last_verdict_allows_repair(str(cwd), session_id):
                deny_reasons.append(
                    "semantic_repair_without_fail_or_gate_blocker: @gate-repair разрешён только после @verify VERDICT: FAIL/BLOCKED или repairable gate-runtime error"
                )

        if norm in {"verify", "verify-implement"} and agent_enabled("verify", str(cwd) or None):
            if st.get("verify_done") and (str(st.get("verify_verdict") or "").upper() == "PASS"):
                deny_reasons.append(
                    "verify_already_pass: VERDICT: PASS уже есть — не повторять @verify; "
                    "пиши FINISH (Handoff/step) и stop. "
                    "Retry @verify разрешён только после FAIL или spawn DENY."
                )
            elif cwd and is_epic_loop_env():
                ac = Path(cwd) / "memory-bank" / "activeContext.md"
                if not ac.is_file():
                    deny_reasons.append(
                        "context_missing: нет memory-bank/activeContext.md — "
                        "сначала Write step + Handoff, потом @verify"
                    )
            if cwd and not deny_reasons:
                deny_reasons.extend(verify_step_path_violations(str(cwd), prompt))
            incomplete = int(st.get("verify_incomplete") or 0)
            no_verdict_retries = int(st.get("verify_no_verdict_retries") or 0)
            if incomplete >= 1 and no_verdict_retries >= 1:
                deny_reasons.append(
                    "verify_no_verdict: retry без VERDICT исчерпан — "
                    "в Handoff `NEED_HUMAN: verify_no_verdict` и stop "
                    "(не плодить @verify; stop-gate разрешит stop)"
                )

        if deny_reasons:
            if managed or any(
                key in reason
                for reason in deny_reasons
                for key in ("managed_in_flight", "model_in_flight")
            ):
                if any("scope_disabled" in reason for reason in deny_reasons):
                    counter = "spawn_denied_scope"
                elif any(
                    key in reason
                    for reason in deny_reasons
                    for key in ("managed_in_flight", "model_in_flight")
                ):
                    counter = "spawn_denied_inflight"
                else:
                    counter = "spawn_denied_config"
                st[counter] = int(st.get(counter) or 0) + 1
                save_state(session_id, str(cwd), st)

            reason = (
                f"spawn DENY [{norm}]: " + " | ".join(deny_reasons)
                if managed
                or any(
                    key in r
                    for r in deny_reasons
                    for key in ("managed_in_flight", "model_in_flight")
                )
                else f"spawn-gate [{norm}]: " + " | ".join(deny_reasons)
            )
            extra = (
                "В Handoff зафиксируй `NEED_HUMAN: verify_no_verdict` и остановись "
                "(не FINISH шага, не новый @verify)."
                if any("verify_no_verdict" in r for r in deny_reasons)
                else f"Исправь prompt/blockers → retry @{norm} (не FINISH)."
            )
            return DecisionEnvelope.deny(
                reason,
                diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY,
                metadata={
                    "additional_context": f"spawn-gate DENY [{norm}]: subagent НЕ запущен. {reason} {extra}",
                    "permissionDecisionReason": reason,
                },
            )

        if managed:
            st["spawn_allowed"] = int(st.get("spawn_allowed") or 0) + 1
        if norm:
            mark_in_flight(
                st,
                agent=norm,
                model=spawn_model,
                managed=managed,
                tool_use_id=(
                    str(payload["tool_use_id"])
                    if payload.get("tool_use_id")
                    else None
                ),
                cwd=str(cwd),
                session_id=session_id,
            )
        if managed:
            spawns = st.setdefault("spawns", [])
            spawns.append(norm)
            st["spawns"] = spawns[-30:]
            if norm in {"verify", "verify-implement"} and agent_enabled("verify", str(cwd) or None):
                st["need_verify"] = True
                incomplete = int(st.get("verify_incomplete") or 0)
                if incomplete >= 1:
                    st["verify_no_verdict_retries"] = (
                        int(st.get("verify_no_verdict_retries") or 0) + 1
                    )
                    st["verify_incomplete"] = 0
            if norm == "gate-repair":
                st["repair_in_flight"] = True
            if norm == "reviewer" and agent_enabled("reviewer", str(cwd) or None):
                st["need_reviewer"] = True
        if norm:
            save_state(session_id, str(cwd), st)

        ctx = (
            f"spawn-gate: launching {tool_input.get('subagent_type') or raw_type}. "
            "CC делегирует как обычно; gate’ы verify — ALLOW READ (implement+decompose yaml); "
            "reviewer — packed Suite/AC/ALLOW. "
            "Parallel managed / same-model spawn — DENY until SubagentStop."
        )
        if notes:
            ctx += " Adjusted: " + "; ".join(notes) + "."

        return DecisionEnvelope.allow(
            updated_input=tool_input,
            reason=ctx,
            metadata={
                "additional_context": ctx,
                "permissionReason": ctx,
            },
        )


class BashPolicyAdapter:
    """Enforces Bash restrictions on gate state, active context, dirty worktree, runner CLI, and search scope."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        tool_name = str(context.tool_name or "").strip()
        if tool_name not in BASH_TOOL_NAMES:
            return None

        cmd = str(context.tool_input.get("command") or "")
        cwd = product_cwd(context.cwd)

        reason = bash_gate_state_write_deny_reason(cmd)
        if not reason:
            reason = bash_active_context_write_deny_reason(cwd, cmd)
        if not reason and is_epic_loop_env():
            reason = bash_discard_dirty_deny_reason(cmd)
        if not reason and is_epic_loop_env():
            reason = runner_cli_deny_reason(cmd)

        # Check search scope enforcement inside EPIC_LOOP
        if not reason and is_epic_loop_env() and is_search_command_line(cmd):
            resolver = ScopeResolver(project_root=cwd)
            payload = context.raw_payload or {}
            graphify_evidence = payload.get("graphify_evidence") or context.tool_input.get("graphify_evidence")
            exception_reason = payload.get("exception_reason") or context.tool_input.get("exception_reason")
            allowed, search_reason, details = resolver.evaluate_search(
                command=cmd,
                cwd=cwd,
                graphify_evidence=graphify_evidence,
                exception_reason=exception_reason,
            )
            if not allowed:
                diag = details.get("diagnostic", search_reason)
                reason = f"search_outside_scope_denied: {diag}"

        if not reason:
            return None

        return DecisionEnvelope.deny(
            reason,
            diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY,
            metadata={
                "additional_context": f"bash-pretool DENY: {reason}",
                "permissionDecisionReason": reason,
            },
        )


class WritePolicyAdapter:
    """Enforces Write/Edit restrictions on gate state, activeContext, recorded artifacts, and context invalidation."""

    def evaluate(self, context: EventContext) -> DecisionEnvelope | None:
        tool_name = str(context.tool_name or "").strip()
        if tool_name not in WRITE_TOOL_ALIASES:
            return None

        tool_input = context.tool_input or {}
        file_path = str(
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("notebook_path")
            or ""
        )
        contents = str(
            tool_input.get("contents")
            or tool_input.get("content")
            or tool_input.get("new_string")
            or ""
        )
        cwd = product_cwd(context.cwd)

        reason = gate_state_write_deny_reason(cwd, file_path)
        if not reason:
            reason = active_context_write_deny_reason(cwd, file_path, contents)
        if not reason:
            reason = recorded_artifact_write_deny_reason(cwd, file_path)

        if reason:
            return DecisionEnvelope.deny(
                reason,
                diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY,
                metadata={
                    "additional_context": (
                        "write-pretool DENY: live loop owns activeContext. "
                        "В chat пиши Handoff / step markdown (не Write/Edit activeContext.md; "
                        "finalize-step / mb-finish обновят activeContext канонически)."
                    ),
                    "permissionDecisionReason": reason,
                },
            )

        payload = dict(context.raw_payload or {})
        if not payload:
            payload = {
                "tool_name": tool_name,
                "tool_input": dict(tool_input),
                "cwd": str(cwd),
                "session_id": context.session_id,
            }

        # Context ledger invalidation for write boundary across actors
        ok, r_code, resp = evaluate_write_payload(payload, provider="claude", cwd=cwd)
        out_meta = resp.get("hookSpecificOutput", {})
        if not ok:
            deny_reason = out_meta.get("permissionDecisionReason") or resp.get("reason_code") or r_code
            return DecisionEnvelope.deny(
                deny_reason,
                diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY,
                metadata=out_meta,
            )

        return DecisionEnvelope.allow(
            reason="write_allowed",
            metadata=out_meta,
        )


def create_pretool_branches() -> list[DispatchBranch]:
    """Assemble the canonical ordered branches for PreToolUse dispatch."""
    return [
        DispatchBranch("project_boundary", ProjectBoundaryAdapter().evaluate, order=10),
        DispatchBranch("finish_boundary", FinishBoundaryAdapter().evaluate, order=20),
        DispatchBranch("agent_policy", AgentPolicyAdapter().evaluate, order=30),
        DispatchBranch("bash_policy", BashPolicyAdapter().evaluate, order=40),
        DispatchBranch("write_policy", WritePolicyAdapter().evaluate, order=50),
    ]


def dispatch_pretool_event(context: EventContext | dict[str, Any]) -> DecisionEnvelope:
    """Convenience helper to dispatch a PreToolUse event through all canonical branches."""
    return dispatch_pretool(context, create_pretool_branches())
