#!/usr/bin/env python3
"""PreToolUse Agent — normalize type, contract gate, strip worktree/model, HARD RULE."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    product_cwd,  # noqa: E402
    agent_enabled,
    agent_model_env_key,
    agent_model_from_project_env,
    HARD_RULE,
    VERDICT_FIRST_LINE,
    allow_read_violations,
    emit,
    in_flight_deny_reasons,
    is_epic_loop_env,
    load_state,
    merged_project_env_map,
    mark_in_flight,
    missing_contract_sections,
    normalize_agent_tool_input,
    normalize_type,
    read_stdin,
    resolved_spawn_model,
    save_state,
    verify_step_path_violations,
    workflow_state_active,
    _discover_registry,
)


def main() -> None:
    data = read_stdin()
    if data.get("tool_name") not in {"Agent", "Task"}:
        return

    tool_input = dict(data.get("tool_input") or {})
    raw_type = tool_input.get("subagent_type") or tool_input.get("agent_type")
    norm = normalize_type(raw_type)
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    st = load_state(session_id, cwd)
    if not workflow_state_active(st, cwd or None):
        return

    if norm and norm != raw_type:
        tool_input["subagent_type"] = norm

    registry = _discover_registry(cwd or None)
    definition = registry.get(norm) if norm else None
    context = "loop" if is_epic_loop_env() else "chat"
    env_models = merged_project_env_map(cwd or None)

    prompt = tool_input.get("prompt") or ""
    if HARD_RULE not in prompt:
        prompt = (prompt.rstrip() + "\n\n" + HARD_RULE).lstrip()
        tool_input["prompt"] = prompt

    notes = normalize_agent_tool_input(tool_input, norm, cwd or None)
    prompt = tool_input.get("prompt") or prompt

    deny_reasons_early: list[str] = []

    if norm in {"verify", "reviewer"} and VERDICT_FIRST_LINE not in prompt:
        prompt = (prompt.rstrip() + "\n\n" + VERDICT_FIRST_LINE).lstrip()
        tool_input["prompt"] = prompt

    deny_reasons: list[str] = list(deny_reasons_early)
    managed = bool(definition is not None and definition.managed)
    is_gate = bool(definition is not None and definition.mode == "gate")
    if definition is not None and definition.managed:
        enabled = definition.loop_enabled if context == "loop" else definition.chat_enabled
        if not enabled:
            deny_reasons.append(
                f"scope_disabled (context={context}); включи _MODEL_{context.upper()}=1"
            )
        else:
            pinned = (env_models.get(agent_model_env_key(norm)) or "").strip()
            if pinned not in (None, "", "inherit"):
                tool_input["model"] = pinned
            elif definition.model not in (None, "inherit"):
                tool_input["model"] = definition.model
        if not definition.overlay.allow_worktree:
            tool_input.pop("isolation", None)
    spawn_model = resolved_spawn_model(tool_input, definition)
    if spawn_model in (None, "", "inherit") and norm:
        pinned = (env_models.get(agent_model_env_key(norm)) or "").strip()
        if pinned not in (None, "", "inherit"):
            spawn_model = pinned
            if managed and not tool_input.get("model"):
                tool_input["model"] = pinned
    if norm and not deny_reasons:
        deny_reasons.extend(
            in_flight_deny_reasons(
                st,
                agent=norm,
                model=spawn_model,
                managed=managed,
            )
        )
    if is_gate and agent_enabled(norm, cwd or None):
        missing = missing_contract_sections(norm, prompt)
        if missing:
            deny_reasons.append(
                f"prompt_incomplete: нет секций [{', '.join(missing)}]. "
                "Добавь заголовки с новой строки "
                "(ASCII `AC-` ок; Unicode `AC−` ок; `# AC+` ок). Нужны: "
                + (
                    "Suite results / AC+ / AC- / 0.11 / ALLOW READ"
                    if norm == "reviewer"
                    else "AC+ / AC- / 0.11 / VERIFY / ALLOW READ"
                )
            )
        for v in allow_read_violations(prompt):
            deny_reasons.append(v)

    if norm == "verify" and agent_enabled("verify", cwd or None):
        if st.get("verify_done") and (
            str(st.get("verify_verdict") or "").upper() == "PASS"
        ):
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
            deny_reasons.extend(verify_step_path_violations(cwd, prompt))
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
            save_state(session_id, cwd, st)
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
            else (
                f"Исправь prompt/blockers → retry @{norm} (не FINISH)."
            )
        )
        emit(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                    "additionalContext": (
                        f"spawn-gate DENY [{norm}]: subagent НЕ запущен. "
                        f"{reason} {extra}"
                    ),
                }
            }
        )
        return

    if managed:
        st["spawn_allowed"] = int(st.get("spawn_allowed") or 0) + 1
    if norm:
        mark_in_flight(
            st,
            agent=norm,
            model=spawn_model,
            managed=managed,
            tool_use_id=(
                str(data["tool_use_id"])
                if data.get("tool_use_id")
                else None
            ),
        )
    if managed:
        spawns = st.setdefault("spawns", [])
        spawns.append(norm)
        st["spawns"] = spawns[-30:]
        if norm == "verify" and agent_enabled("verify", cwd or None):
            st["need_verify"] = True
            incomplete = int(st.get("verify_incomplete") or 0)
            if incomplete >= 1:
                st["verify_no_verdict_retries"] = (
                    int(st.get("verify_no_verdict_retries") or 0) + 1
                )
                st["verify_incomplete"] = 0
        if norm == "reviewer" and agent_enabled("reviewer", cwd or None):
            st["need_reviewer"] = True
    if norm:
        save_state(session_id, cwd, st)

    ctx = (
        f"spawn-gate: launching {tool_input.get('subagent_type') or raw_type}. "
        "CC делегирует как обычно; gate’ы verify/reviewer — packed prompt. "
        "Parallel managed / same-model spawn — DENY until SubagentStop."
    )
    if notes:
        ctx += " Adjusted: " + "; ".join(notes) + "."

    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": tool_input,
                "additionalContext": ctx,
            }
        }
    )


if __name__ == "__main__":
    main()
