"""Build a command-first, runtime- and workflow-scoped prompt context.

This module does not resolve or read workflow files. The active runtime
entrypoint and ``mainrule.mdc`` remain the single routing source; the agent
reads the selected command chain itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

_ROLE_ALIASES = {
    "BACK": "BACK",
    "FRONT": "FRONT",
    "INTEG": "INTEG",
    "INTEGRATION": "INTEG",
}
_TOKEN_RE = re.compile(r"[^\s`]+")


@dataclass(frozen=True)
class PromptScope:
    """The minimum command-specific data needed by a prompt renderer."""

    command: str
    role: str
    phase: str
    step: str
    epic: str
    runtime: str = "claude-code"
    entrypoint: str = "CLAUDE.md"
    # Kept for API compatibility with runner metadata. Workflow paths are
    # deliberately not resolved by the prompt builder.
    workflow_file: str | None = None
    pack_id: str | None = None
    diagnostics: tuple[str, ...] = ()


def _canonical_role(raw: object, *, default: str = "") -> str:
    value = str(raw or "").strip().upper()
    if not value:
        return default
    return _ROLE_ALIASES.get(value, value)


def _runtime_name(raw: object) -> str:
    value = str(raw or "claude-code").strip().lower().replace("_", "-")
    if value in {"codex", "codex-cli", "codex-app"}:
        return "codex"
    return "claude-code"


def _runtime_entrypoint(runtime: str) -> str:
    return "AGENTS.md" if runtime == "codex" else "CLAUDE.md"


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
        phase_tokens = [token for token in tokens[1:] if not token.startswith("@")]
        phase = " ".join(phase_tokens).upper()
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
    runtime: str | None = None,
) -> PromptScope:
    """Build one command scope without resolving or loading workflow files.

    Workflow routing remains the responsibility of the runtime entrypoint and
    ``mainrule.mdc``. This builder only renders the command, role, mode and
    the correct entrypoint contract for the selected runtime.
    """

    # Keep the public cwd parameter for callers that build prompts from a
    # project root. The prompt builder must not inspect that root for routes.
    _ = Path(cwd)
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

    runtime_name = _runtime_name(runtime)

    return PromptScope(
        command=normalized_command,
        role=role,
        phase=phase,
        step=_projection_value(projection, "step", "next_step") or "unknown",
        epic=_projection_value(projection, "epic", "epic_id") or "unknown",
        runtime=runtime_name,
        entrypoint=_runtime_entrypoint(runtime_name),
    )


def render_prompt_scope(scope: PromptScope) -> str:
    """Render the command scope as the first, standalone prompt block."""

    lines = [
        f"COMMAND: {scope.command}",
        "## CURRENT WORKFLOW SCOPE (HARD)",
        f"- runtime: `{scope.runtime}`",
        f"- entrypoint: `{scope.entrypoint}`",
        f"- role: `{scope.role}`",
        f"- phase: `{scope.phase or 'unknown'}`",
        f"- step: `{scope.step}`",
        f"- epic: `{scope.epic}`",
        "- HARD READ: прочитай только указанный entrypoint.",
        "- HARD READ: затем прочитай `.cursor/rules/mainrule.mdc`.",
        "- HARD READ: по таблице mainrule выбери текущую роль и режим.",
        "- HARD READ: загрузи цепочку связанных файлов выбранной role/mode chain, Gates и ссылок.",
        "- Scope lock: не загружай инструкции других ролей, фаз или команд.",
    ]
    if scope.diagnostics:
        lines.append("- scope diagnostics: " + ", ".join(scope.diagnostics))
    return "\n".join(lines) + "\n"


__all__ = ["PromptScope", "build_prompt_scope", "render_prompt_scope"]
