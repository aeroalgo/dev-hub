#!/usr/bin/env python3
"""SubagentStart — inject per-agent contract into child context."""
from __future__ import annotations

import sys
import re
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    product_cwd,  # noqa: E402
    HARD_RULE,
    check_contract_drift,
    current_gate_identity,
    emit,
    load_state,
    mark_in_flight,
    normalize_type,
    read_stdin,
    workflow_state_active,
    resolved_spawn_model,
    save_state,
    _discover_registry,
)
from loop.runtime_adapters.agent_contract import get_agent_contract_adapter
from loop.runtime_materializers.agent_policy import get_always_inject_set


_ALWAYS_INJECT = get_always_inject_set()
_AGENT_TYPE_FIELDS = ("agent_type", "subagent_type", "type")
PRESET_BY_AGENT = {
    "verify": "preset.verify",
    "verify-implement": "preset.verify",
    "verify-bugfix": "preset.verify",
    "verify-qa": "preset.reviewer",
    "verify-decompose": "preset.verify",
    "analyze-verify": "preset.verify",
    "reviewer": "preset.reviewer",
    "explorer": "preset.explorer",
    "gate-repair": "preset.repair",
    "reconcile-verify": "preset.explorer",
    "sunset-inventory": "preset.explorer",
    "verify-script": "preset.verify",
    "verify-edit": "preset.verify",
    "verify-publish": "preset.verify",
}


def _resolve_agent_type(data: dict[str, object]) -> str | None:
    for field in _AGENT_TYPE_FIELDS:
        raw = data.get(field)
        if isinstance(raw, str) and raw.strip():
            return normalize_type(raw.strip().lower())
    nested = data.get("tool_input")
    if isinstance(nested, dict):
        for field in _AGENT_TYPE_FIELDS:
            raw = nested.get(field)
            if isinstance(raw, str) and raw.strip():
                return normalize_type(raw.strip().lower())
    prompt = "\n".join(
        str(data.get(field) or "")
        for field in ("prompt", "task", "instructions", "message")
    )
    if isinstance(nested, dict):
        prompt += "\n" + str(nested.get("prompt") or "")
    match = re.search(r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)", prompt)
    if match:
        return normalize_type(match.group(1))
    for token in (
        "gate-repair",
        "verify-bugfix",
        "verify-implement",
        "verify-qa",
        "verify-decompose",
        "analyze-verify",
        "verify-script",
        "verify-edit",
        "verify-publish",
        "reconcile-verify",
    ):
        if token in prompt.lower():
            return token
    return None


def _gate_session_id(data: dict[str, object]) -> str:
    for field in ("parent_session_id", "root_session_id"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    inherited = str(os.environ.get("EPIC_RUNNER_SESSION_ID") or "").strip()
    if inherited and (
        data.get("runtime_id") == "codex"
        or os.environ.get("EPIC_RUNTIME") == "codex"
        or os.environ.get("EPIC_RUNTIME_RESOLVED") == "codex"
    ):
        return inherited
    return str(data.get("session_id") or "").strip()


def main() -> None:
    data = read_stdin()
    agent_type = _resolve_agent_type(data)
    session_id = _gate_session_id(data)
    cwd = str(product_cwd(data.get("cwd") or ""))
    runtime_id = str(data.get("runtime_id") or os.environ.get("EPIC_RUNTIME") or "universal")
    contract_adapter = get_agent_contract_adapter(runtime_id)
    contract = contract_adapter.contract(agent_type)
    if not contract:
        return

    is_ok, drift_msg = check_contract_drift(agent_type)
    if not is_ok:
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStart",
                    "permissionDecision": "deny",
                    "additionalContext": f"DENY: {drift_msg}",
                }
            }
        )
        return

    definition = _discover_registry(cwd or None).get(agent_type) if agent_type else None
    is_codex = (
        str(data.get("runtime_id") or "").lower() == "codex"
        or os.environ.get("EPIC_RUNTIME") == "codex"
        or os.environ.get("EPIC_RUNTIME_RESOLVED") == "codex"
    )
    # verify/reviewer always get their contract — regardless of workflow state
    if agent_type not in _ALWAYS_INJECT:
        st = load_state(session_id, cwd)
        if not workflow_state_active(st, cwd or None) and not (is_codex and definition and definition.managed):
            return
    if is_codex and definition and definition.managed:
        st = load_state(session_id, cwd)
        if workflow_state_active(st, cwd or None) or agent_type in _ALWAYS_INJECT:
            active = st.get("in_flight") or []
            incoming_tool_id = str(data.get("tool_use_id") or data.get("thread_id") or "")
            if not any(
                str(entry.get("agent") or "") == agent_type
                and (
                    not incoming_tool_id
                    or str(entry.get("tool_use_id") or "") in {"", incoming_tool_id}
                )
                for entry in active
            ):
                mark_in_flight(
                    st,
                    agent=agent_type,
                    model=resolved_spawn_model({}, definition),
                    managed=True,
                    tool_use_id=str(data.get("tool_use_id") or data.get("thread_id") or "") or None,
                )
                st.setdefault("spawns", []).append(agent_type)
                if agent_type in {
                    "verify",
                    "verify-implement",
                    "verify-bugfix",
                    "verify-qa",
                    "verify-decompose",
                    "analyze-verify",
                    "verify-script",
                    "verify-edit",
                    "verify-publish",
                }:
                    st["need_verify"] = True
                if agent_type == "gate-repair":
                    st["repair_in_flight"] = True
                save_state(session_id, cwd, st)
    identity = current_gate_identity(cwd, session_id)
    identity_session = str(identity.get("session_id") or session_id or "").strip()
    identity_epic = str(identity.get("epic_id") or "").strip()
    identity_step = str(identity.get("step") or "").strip()
    identity_block = (
        f"GATE_IDENTITY session_id={identity_session} "
        f"epic_id={identity_epic} step_id={identity_step}\n"
        "Fence MUST use these exact IDs for session_id, epic_id, and step_id.\n"
    )
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": (
                    f"agent_type={agent_type} preset={PRESET_BY_AGENT.get(agent_type, '')}\n"
                    f"{identity_block}"
                    f"{contract}\n{HARD_RULE}"
                ),
            }
        }
    )


if __name__ == "__main__":
    main()
