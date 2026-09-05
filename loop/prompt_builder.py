"""Build a command-first, workflow-scoped prompt context.

This module deliberately resolves pointers only.  It does not read workflow
files or create a runtime chain; the agent is responsible for reading the
declared command scope and following its links.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from loop.workflow.command_router import route_command
from loop.workflow.registry import resolve_workflow_pack


_ROLE_ALIASES = {
    "BACK": "BACK",
    "FRONT": "FRONT",
    "INTEG": "INTEG",
    "INTEGRATION": "INTEG",
}
_ROLE_DIRS = {
    "BACK": "back_developer",
    "FRONT": "front_developer",
    "INTEG": "integration_developer",
}
_NO_WORKFLOW_PHASES = frozenset({"", "UNKNOWN", "DONE"})
_TOKEN_RE = re.compile(r"[^\s`]+")


@dataclass(frozen=True)
class PromptScope:
    """The minimum command-specific data needed by a prompt renderer."""

    command: str
    role: str
    phase: str
    step: str
    epic: str
    workflow_file: str | None
    pack_id: str | None = None
    diagnostics: tuple[str, ...] = ()


def _canonical_role(raw: object, *, default: str = "") -> str:
    value = str(raw or "").strip().upper()
    if not value:
        return default
    return _ROLE_ALIASES.get(value, value)


def _role_dir(role: str) -> str:
    return _ROLE_DIRS.get(role, f"{role.lower()}_developer")


def _projection_value(projection: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = projection.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _command_parts(
    raw_command: object,
    *,
    fallback_role: str,
    fallback_phase: str,
) -> tuple[str, str]:
    raw = str(raw_command or "").strip()
    tokens = _TOKEN_RE.findall(raw)
    if tokens and tokens[0].upper() == "COMMAND:" and len(tokens) > 1:
        tokens = tokens[1:]

    role = _canonical_role(fallback_role, default="")
    phase = str(fallback_phase or "").strip().upper()
    if not tokens:
        return role, phase

    first = tokens[0].upper()
    known_role = _canonical_role(first, default="")
    if len(tokens) >= 2 and (first in _ROLE_ALIASES or first.isalpha()):
        role = known_role or first
        phase = tokens[1].upper()
    elif not phase:
        phase = first

    return role, phase


def _fallback_command(projection: dict[str, Any], fallback: str | None) -> str:
    phase = _projection_value(projection, "phase", "mode", "loop_phase")
    role = _projection_value(projection, "role")
    if phase:
        phase_tokens = _TOKEN_RE.findall(phase)
        if phase_tokens and phase_tokens[0].upper() in _ROLE_ALIASES and len(phase_tokens) > 1:
            return phase
        return f"{role} {phase}".strip() if role else phase
    if fallback and str(fallback).strip():
        return str(fallback).strip()
    return "UNKNOWN"


def build_prompt_scope(
    cwd: str | Path,
    *,
    projection: dict[str, Any] | None = None,
    command: str | None = None,
    fallback_command: str | None = None,
) -> PromptScope:
    """Resolve one command and its one workflow pointer.

    The function is intentionally tolerant: a malformed/unknown pack produces
    diagnostics in the scope instead of preventing a prompt from being
    written.  No workflow contents are loaded here.
    """

    root = Path(cwd).resolve()
    projection = dict(projection or {})
    raw = command or _fallback_command(projection, fallback_command)
    fallback_role = _projection_value(projection, "role")
    fallback_phase = _projection_value(projection, "phase", "mode", "loop_phase")
    role, phase = _command_parts(
        raw,
        fallback_role=fallback_role,
        fallback_phase=fallback_phase,
    )

    if not role and phase and str(raw).strip().upper() != "UNKNOWN":
        role = _canonical_role(fallback_role, default="BACK")
    if not phase and role:
        phase = "IMPLEMENT"

    if role and phase:
        normalized_command = f"{role} {phase}"
    else:
        normalized_command = "UNKNOWN"
        role = role or "UNKNOWN"
        phase = phase or ""

    workflow_file: str | None = None
    pack_id: str | None = None
    diagnostics: list[str] = []
    if phase not in _NO_WORKFLOW_PHASES and role != "UNKNOWN":
        try:
            pack_result = resolve_workflow_pack(cwd=root)
            pack_id = pack_result.pack_id or None
            diagnostics.extend(str(item) for item in pack_result.diagnostic_codes)
            if pack_result.ok and pack_result.pack is not None:
                route = route_command(pack_result.pack, normalized_command)
                workflow_file = route.rules_mdc_rel
            elif not diagnostics:
                diagnostics.append("workflow_pack_unresolved")
        except Exception as exc:  # pragma: no cover - defensive hook boundary
            diagnostics.append(f"workflow_scope_resolve_failed: {exc}")

    return PromptScope(
        command=normalized_command,
        role=role,
        phase=phase,
        step=_projection_value(projection, "step", "next_step") or "unknown",
        epic=_projection_value(projection, "epic", "epic_id") or "unknown",
        workflow_file=workflow_file,
        pack_id=pack_id,
        diagnostics=tuple(diagnostics),
    )


def render_prompt_scope(scope: PromptScope) -> str:
    """Render the command scope as the first, standalone prompt block."""

    lines = [
        f"COMMAND: {scope.command}",
        "## CURRENT WORKFLOW SCOPE (HARD)",
        f"- role: `{scope.role}`",
        f"- phase: `{scope.phase or 'unknown'}`",
        f"- step: `{scope.step}`",
        f"- epic: `{scope.epic}`",
    ]
    if scope.workflow_file:
        lines.append(f"- workflow: `{scope.workflow_file}`")
        lines.extend(
            [
                "- HARD READ: прочитай `CLAUDE.md`, `AGENTS.md` и указанный workflow.",
                "- HARD READ: загрузи всю цепочку связанных файлов по ссылкам и командам из этого workflow.",
            ]
        )
    else:
        lines.append("- workflow: `(unresolved — use the current command context)`")
        lines.append("- HARD READ: прочитай `CLAUDE.md` и `AGENTS.md`; не выдумывай unrelated workflow.")
    lines.append("- Scope lock: не загружай инструкции других ролей, фаз или команд.")
    if scope.diagnostics:
        lines.append("- scope diagnostics: " + ", ".join(scope.diagnostics))
    return "\n".join(lines) + "\n"


__all__ = ["PromptScope", "build_prompt_scope", "render_prompt_scope"]
