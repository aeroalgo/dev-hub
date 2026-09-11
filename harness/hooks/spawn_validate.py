#!/usr/bin/env python3
"""Reusable validation for Agent/Task spawn inputs."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from _lib import (
    GATE_AGENTS,
    HARD_RULE,
    VERDICT_FIRST_LINE,
    _SECTION_PATTERNS,
    agent_enabled,
    agent_model_env_key,
    allow_read_violations,
    allow_write_violations,
    agent_model_from_project_env,
    current_gate_identity,
    in_flight_deny_reasons,
    is_epic_loop_env,
    load_state,
    merged_project_env_map,
    missing_contract_sections,
    normalize_agent_tool_input,
    normalize_type,
    read_stdin,
    repair_blocker_violations,
    resolved_spawn_model,
    verify_bugfix_path_violations,
    verify_decompose_path_violations,
    verify_step_path_violations,
    _discover_registry,
)

GATE_IDENTITY_MARKER = "GATE_IDENTITY session_id="
IDENTITY_SPAWN_AGENTS = frozenset(GATE_AGENTS | {"gate-repair"})


def _resolve_spawn_identity(
    state: dict[str, Any],
    cwd: str | Path | None,
) -> dict[str, str]:
    """Resolve SoT session_id/epic_id/step_id for spawn prompt inject."""
    from loop.gate_identity import GateIdentity

    sid = str(state.get("session_id") or "").strip()
    raw = state.get("gate_identity")
    identity = GateIdentity.from_mapping(raw) if isinstance(raw, dict) else None
    if identity is not None and identity.session_id and identity.epic_id:
        return {
            "session_id": str(identity.session_id).strip(),
            "epic_id": str(identity.epic_id).strip(),
            "step_id": str(identity.step_id or "").strip(),
        }

    if cwd is not None:
        try:
            resolved = current_gate_identity(str(cwd), sid or str(identity.session_id if identity else ""))
        except Exception:
            resolved = {}
        if isinstance(resolved, dict) and resolved:
            merged = GateIdentity.from_mapping(resolved)
            if merged is not None and merged.session_id and merged.epic_id:
                return {
                    "session_id": str(merged.session_id).strip(),
                    "epic_id": str(merged.epic_id).strip(),
                    "step_id": str(merged.step_id or (identity.step_id if identity else "") or "").strip(),
                }
            if not sid:
                sid = str(resolved.get("session_id") or "").strip()

    try:
        from epic.core import load_epic_state

        epic_state = load_epic_state(str(cwd)) if cwd is not None else None
    except Exception:
        epic_state = None
    if epic_state is not None or sid:
        expected = GateIdentity.expected(epic_state, session_id=sid)
        if expected.session_id and expected.epic_id:
            return {
                "session_id": str(expected.session_id).strip(),
                "epic_id": str(expected.epic_id).strip(),
                "step_id": str(expected.step_id or "").strip(),
            }
        if not sid:
            sid = str(expected.session_id or "").strip()

    if identity is None:
        return {"session_id": sid, "epic_id": "", "step_id": ""}
    return {
        "session_id": str(identity.session_id or sid or "").strip(),
        "epic_id": str(identity.epic_id or "").strip(),
        "step_id": str(identity.step_id or "").strip(),
    }


def ensure_gate_identity_prompt(
    tool_input: dict[str, Any],
    state: dict[str, Any],
    *,
    agent_type: str | None,
    cwd: str | Path | None = None,
) -> list[str]:
    """Inject GATE_IDENTITY into spawn prompt or DENY when SoT incomplete.

    PreToolUse consumers apply ``updatedInput`` so the child sees the line
    before run. Missing session_id/epic_id is fail-closed (no silent skip).
    """
    norm = normalize_type(agent_type)
    if not norm or norm not in IDENTITY_SPAWN_AGENTS:
        return []
    if not agent_enabled(norm, str(cwd) if cwd is not None else None):
        return []

    prompt = str(tool_input.get("prompt") or "")
    if GATE_IDENTITY_MARKER in prompt:
        return []

    fields = _resolve_spawn_identity(state, cwd)
    sess = fields["session_id"]
    epic = fields["epic_id"]
    step = fields["step_id"]
    if not sess or not epic:
        return [
            "prompt_incomplete:GATE_IDENTITY: нужны session_id и epic_id "
            "(SoT gate_identity / session_start_identity); "
            "добавь `GATE_IDENTITY session_id=<id> epic_id=<epic> step_id=<step>` "
            "или подготовь session identity до spawn"
        ]

    from loop.gate_identity import GateIdentity

    inject = GateIdentity.inject_text(
        {"session_id": sess, "epic_id": epic, "step_id": step}
    )
    tool_input["prompt"] = (inject + "\n" + prompt.lstrip()).rstrip() + "\n"
    return []


def validate_spawn_input(
    tool_input: dict[str, Any],
    state: dict[str, Any],
    cwd: str | Path | None = None,
) -> tuple[list[str], list[str]]:
    """Normalize a spawn and return ``(deny_reasons, notes)``.

    The function mutates ``tool_input`` only for the established hook contract:
    type aliases, HARD RULE/VERDICT/GATE_IDENTITY requirements, worktree
    removal, and model pinning.  It does not mutate the persisted spawn state.
    """
    raw_type = tool_input.get("subagent_type") or tool_input.get("agent_type")
    norm = normalize_type(raw_type)
    if norm and norm != raw_type:
        tool_input["subagent_type"] = norm

    project_dir = str(cwd) if cwd is not None else None
    registry = _discover_registry(project_dir)
    definition = registry.get(norm) if norm else None
    context = "loop" if is_epic_loop_env() else "chat"
    env_models = merged_project_env_map(project_dir)

    prompt = tool_input.get("prompt") or ""
    if HARD_RULE not in prompt:
        prompt = (prompt.rstrip() + "\n\n" + HARD_RULE).lstrip()
        tool_input["prompt"] = prompt

    notes = normalize_agent_tool_input(tool_input, norm, project_dir)
    prompt = tool_input.get("prompt") or prompt

    if norm in {"verify", "reviewer", "verify-implement", "verify-bugfix", "verify-qa", "verify-decompose", "analyze-verify", "verify-script", "verify-edit", "verify-publish"} and VERDICT_FIRST_LINE not in prompt:
        prompt = (prompt.rstrip() + "\n\n" + VERDICT_FIRST_LINE).lstrip()
        tool_input["prompt"] = prompt

    deny_reasons: list[str] = []
    deny_reasons.extend(
        ensure_gate_identity_prompt(tool_input, state, agent_type=norm, cwd=cwd)
    )
    prompt = tool_input.get("prompt") or prompt
    managed = bool(definition is not None and definition.managed)
    is_gate = bool(definition is not None and definition.mode == "gate")
    is_repair = bool(definition is not None and definition.mode == "repair")
    runtime = os.environ.get("EPIC_RUNTIME_RESOLVED") or os.environ.get("EPIC_RUNTIME")
    if definition is not None and definition.managed:
        enabled = definition.loop_enabled if context == "loop" else definition.chat_enabled
        if not enabled:
            deny_reasons.append(
                f"scope_disabled (context={context}); включи _MODEL_{context.upper()}=1"
            )
        else:
            pinned = (
                agent_model_from_project_env(norm, project_dir)
                if runtime == "codex"
                else (env_models.get(agent_model_env_key(norm)) or "").strip()
            )
            if pinned not in (None, "", "inherit"):
                tool_input["model"] = pinned
        if not definition.overlay.allow_worktree:
            tool_input.pop("isolation", None)

    spawn_model = resolved_spawn_model(tool_input, definition)
    if spawn_model in (None, "", "inherit") and norm:
        pinned = (
            agent_model_from_project_env(norm, project_dir)
            if runtime == "codex"
            else (env_models.get(agent_model_env_key(norm)) or "").strip()
        )
        if pinned not in (None, "", "inherit"):
            spawn_model = pinned
            if managed and not tool_input.get("model"):
                tool_input["model"] = pinned

    if norm and not deny_reasons:
        deny_reasons.extend(
            in_flight_deny_reasons(
                state,
                agent=norm,
                model=spawn_model,
                managed=managed,
            )
        )
    if is_gate and agent_enabled(norm, project_dir):
        missing = missing_contract_sections(norm, prompt)
        if missing:
            needed_str = " / ".join([label for label, _ in _SECTION_PATTERNS.get(norm, [])])
            if norm in {"verify", "verify-implement"}:
                hint = (
                    "Нужны: ALLOW READ (implement yaml + decompose yaml + code). "
                    "Checklist SoT = decompose shard — AC+/AC−/§0.11/VERIFY в prompt не обязательны."
                )
            elif norm == "verify-bugfix":
                hint = (
                    "Нужны: ALLOW READ с bugfix artifact "
                    "`memory-bank/**/bugfix/**/bugfix-*.md`."
                )
            elif norm == "verify-decompose":
                hint = (
                    "Нужны: ALLOW READ с plan.md + yaml/decompose-index.yaml "
                    "(coverage SoT = shards, не packed COVERAGE)."
                )
            elif norm in {"verify-qa", "reviewer"}:
                hint = (
                    "Нужны: Suite results + ALLOW READ "
                    "(AC matrix SoT = Frozen QA checklist)."
                )
            else:
                hint = (
                    "Добавь заголовки с новой строки "
                    "(ASCII `AC-` ок; Unicode `AC−` ок; `# AC+` ок). Нужны: "
                    + (needed_str if needed_str else (
                        "Suite results / ALLOW READ"
                        if norm == "reviewer"
                        else "AC+ / AC- / 0.11 / VERIFY / ALLOW READ"
                    ))
                )
            deny_reasons.append(
                f"prompt_incomplete: нет секций [{', '.join(missing)}]. " + hint
            )
        for violation in allow_read_violations(prompt, agent_type=norm):
            if "ALLOW READ пуст" in violation and "memory-bank/" in prompt:
                violation = violation.replace(
                    "ALLOW READ пуст", "ALLOW READ содержит деревья/каталоги: memory-bank/"
                )
            deny_reasons.append(violation)
        if project_dir and not missing:
            if norm in {"verify", "verify-implement"}:
                deny_reasons.extend(verify_step_path_violations(project_dir, prompt))
            elif norm == "verify-bugfix":
                deny_reasons.extend(verify_bugfix_path_violations(project_dir, prompt))
            elif norm == "verify-decompose":
                deny_reasons.extend(verify_decompose_path_violations(project_dir, prompt))
        if norm in {"verify-qa", "reviewer"}:
            try:
                from loop.qa_checklist_freeze import spawn_freeze_violations

                deny_reasons.extend(spawn_freeze_violations(prompt, state))
            except Exception:
                pass

    if is_repair and agent_enabled(norm, project_dir):
        missing = missing_contract_sections(norm, prompt)
        if missing:
            needed_str = " / ".join([label for label, _ in _SECTION_PATTERNS.get(norm, [])])
            deny_reasons.append(
                f"prompt_incomplete: нет секций [{', '.join(missing)}]. "
                "Нужны: " + (needed_str or "BLOCKERS / ALLOW WRITE / VERIFY")
            )
        for violation in allow_write_violations(prompt):
            deny_reasons.append(violation)
        for violation in repair_blocker_violations(prompt):
            deny_reasons.append(violation)
        for violation in allow_read_violations(prompt):
            if "ALLOW READ пуст" in violation:
                continue
            deny_reasons.append(violation)
        qa_repair = bool(re.search(r"(?i)(?:BACK\s+QA|verify-qa)", prompt))
        verify_match = re.search(r"(?im)^\s*(?:#+\s*)?VERIFY\b[^\n]*", prompt)
        verify_start = verify_match.end() if verify_match else 0
        allow_read_match = re.search(
            r"(?im)^\s*(?:#+\s*)?ALLOW\s+READ\b", prompt[verify_start:]
        )
        verify_body = prompt[verify_start:]
        if allow_read_match:
            verify_body = verify_body[: allow_read_match.start()]
        first_pytest = verify_body.lower().find("pytest")
        full_suite = verify_body.find("bin/pytest -q --tb=line")
        if qa_repair and (
            full_suite < 0 or (first_pytest >= 0 and full_suite > first_pytest)
        ):
            deny_reasons.append(
                "qa_repair_verify_incomplete: gate-repair после BACK QA обязан "
                "содержать первым VERIFY пунктом `bin/pytest -q --tb=line`; "
                "targeted-команды не заменяют полный suite"
            )

    return deny_reasons, notes


def main() -> None:
    payload = read_stdin()
    tool_name = payload.get("tool_name")
    if tool_name not in {"Agent", "Task"}:
        return
    tool_input = dict(payload.get("tool_input") or {})
    session_id = str(payload.get("session_id") or "")
    cwd = payload.get("cwd")
    state = dict(payload.get("state") or load_state(session_id, str(cwd or "")))
    deny_reasons, notes = validate_spawn_input(tool_input, state, cwd)
    tool_input["state"] = state
    tool_input["session_id"] = session_id
    tool_input["cwd"] = cwd
    tool_input["hook_event_name"] = "PreToolUse"
    tool_input["tool_name"] = tool_name
    tool_input["prompt"] = tool_input.get("prompt") or ""
    tool_input["notes"] = notes
    tool_input["deny_reasons"] = deny_reasons
    tool_input.pop("state", None)
    tool_input.pop("session_id", None)
    tool_input.pop("cwd", None)
    tool_input.pop("hook_event_name", None)
    tool_input.pop("tool_name", None)
    tool_input.pop("notes", None)
    tool_input.pop("deny_reasons", None)
    json.dump(
        {
            "deny_reasons": deny_reasons,
            "notes": notes,
            "tool_input": tool_input,
        },
        sys.stdout,
        ensure_ascii=False,
    )


if __name__ == "__main__":
    main()
