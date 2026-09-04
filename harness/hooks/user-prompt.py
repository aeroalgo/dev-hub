#!/usr/bin/env python3
"""UserPromptSubmit — set spawn-gate mode + inject spawn map."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (
    product_cwd,  # noqa: E402
    AUDIT_RE,
    BUGFIX_RE,
    FINISH_RE,
    IMPL_RE,
    QA_RE,
    agent_enabled,
    build_spawn_map,
    emit,
    is_epic_loop_env,
    registry_active_agents,
    current_gate_identity,
    _discover_registry,
    load_state,
    neutralize_state,
    read_stdin,
    save_state,
    sync_gate_identity,
    workflow_hooks_enabled,
)
from epic_lib import gates_from_phase, load_epic_state  # noqa: E402


def main() -> None:
    data = read_stdin()
    prompt = data.get("prompt") or data.get("user_prompt") or ""
    session_id = data.get("session_id") or ""
    cwd = str(product_cwd(data.get("cwd") or ""))
    st = load_state(session_id, cwd)
    projection_phase = None
    projection_gates: dict[str, object] = {}
    if is_epic_loop_env() and cwd:
        try:
            epic_state = load_epic_state(cwd)
            projection = epic_state.get("projection") or {}
            projection_phase = projection.get("phase") or epic_state.get("phase")
            if projection_phase:
                projection_gates = gates_from_phase(projection_phase, cwd=cwd)
        except Exception:
            projection_phase = None
    else:
        projection_phase = None
    projection_authoritative = bool(projection_phase)
    role_prompt = bool(
        QA_RE.search(prompt) or IMPL_RE.search(prompt) or BUGFIX_RE.search(prompt)
    )
    active = workflow_hooks_enabled(cwd or None, role_prompt=role_prompt)

    if not active:
        neutralize_state(st)
        save_state(session_id, cwd, st)
        return

    st["workflow_source"] = "loop" if is_epic_loop_env() else "manual"
    context = "loop" if is_epic_loop_env() else "chat"
    registry = _discover_registry(cwd or None)
    active_agents = registry_active_agents(context, cwd or None)
    active_ids = sorted(active_agents)
    inactive_managed = sorted(
        (
            definition
            for definition in registry.definitions
            if definition.managed
            and definition.id not in active_agents
            and definition.overlay.mode in {"gate", "search", "optional"}
        ),
        key=lambda definition: definition.id,
    )
    policy_line = (
        f"Agent policy: context={context}, revision={registry.revision[:16]}, "
        f"active={','.join(active_ids) or 'none'}"
    )
    if inactive_managed:
        policy_line += ", disabled=" + ",".join(
            f"{definition.id}({definition.overlay.mode})"
            for definition in inactive_managed
        )
    ctx_parts = [build_spawn_map(cwd or None), policy_line]
    if cwd:
        identity = current_gate_identity(cwd, session_id)
        if sync_gate_identity(st, identity):
            ctx_parts.append("gate identity changed → stale verify/reviewer evidence cleared.")

    if projection_authoritative:
        st["mode"] = projection_gates.get("mode")
        st["need_verify"] = bool(projection_gates.get("need_verify"))
        st["need_reviewer"] = bool(projection_gates.get("need_reviewer"))
        ctx_parts.append(
            "PROJECTION phase=%s → mode/gates определены runner-ом; regex не переопределяет."
            % projection_phase
        )

    if not projection_authoritative and QA_RE.search(prompt):
        st["mode"] = "qa"
        st["need_reviewer"] = agent_enabled("reviewer", cwd or None)
        st["reviewer_done"] = False
        st["reviewer_verdict"] = None
        ctx_parts.append(
            "MODE=QA → после полного planned suite обязательно 1× "
            "Agent/subagent_type=reviewer с Suite results · AC+ · AC− · "
            "§0.11 · ALLOW READ (≤10 файлов). Без reviewer FINISH QA = FAIL."
        )
    elif not projection_authoritative and AUDIT_RE.search(prompt):
        st["mode"] = "audit"
        st["need_verify"] = False
        st["need_reviewer"] = False
        ctx_parts.append(
            "MODE=AUDIT → gap-анализ plan vs implement. "
            "FINISH: audit-YYYYMMDD-*.yaml записан + gap-матрица полна + "
            "новые sNN в decompose index (если ❌). "
            "Next: не_реализовано → BACK IMPLEMENT → снова BACK AUDIT; "
            "всё ✅/⚠️ → BACK QA."
        )
    elif not projection_authoritative and (
        IMPL_RE.search(prompt) or BUGFIX_RE.search(prompt)
    ):
        st["mode"] = "implement"
        st["need_verify"] = agent_enabled("verify", cwd or None)
        if not FINISH_RE.search(prompt):
            st["verify_done"] = False
            st["verify_verdict"] = None
        mode = "BUGFIX" if BUGFIX_RE.search(prompt) else "IMPLEMENT"
        ctx_parts.append(
            f"MODE={mode} → соблюдай spawn-gate. FINISH: seed → flush cp → "
            "evidence (in_progress) → Handoff → @verify → PASS → finalize-step."
        )

    if (
        FINISH_RE.search(prompt)
        and st.get("mode") == "implement"
        and agent_enabled("verify", cwd or None)
    ):
        st["need_verify"] = True
        if st.get("verify_done") and st.get("verify_verdict") == "PASS":
            ctx_parts.append("FINISH detected → @verify уже PASS — не повторять; stop.")
        else:
            ctx_parts.append(
                "FINISH detected → Handoff → @verify до VERDICT: PASS → stop."
            )
    if (
        FINISH_RE.search(prompt)
        and st.get("mode") == "qa"
        and agent_enabled("reviewer", cwd or None)
    ):
        st["need_reviewer"] = True
        ctx_parts.append(
            "QA FINISH detected → @reviewer · qa-*.yaml (verdict) · Handoff → REFLECT."
        )

    if cwd and is_epic_loop_env():
        try:
            armed = str(load_epic_state(cwd).get("armed_step") or "").upper()
        except (ImportError, OSError, TypeError, ValueError):
            armed = ""
        if armed == "DECOMPOSE":
            st["need_verify"] = False
            st["need_reviewer"] = False
            if st.get("mode") == "implement":
                st["mode"] = None
            ctx_parts.append(
                "armed_step=DECOMPOSE → verify/reviewer OFF (docs-only). "
                "FINISH после decompose/index.*; promote DECOMPOSE→IMPLEMENT на prepare."
            )

    save_state(session_id, cwd, st)
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(ctx_parts),
            }
        }
    )


if __name__ == "__main__":
    main()
