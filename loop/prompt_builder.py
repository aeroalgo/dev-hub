"""Build a command-first, runtime- and workflow-scoped prompt context.

This module does not resolve or read workflow files. The active runtime
entrypoint and ``mainrule.mdc`` remain the single routing source; the agent
reads the selected command chain itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Literal

_ROLE_ALIASES = {
    "BACK": "BACK",
    "FRONT": "FRONT",
    "INTEG": "INTEG",
    "INTEGRATION": "INTEG",
}
_TOKEN_RE = re.compile(r"[^\s`]+")

# Canonical phase matrix tokens that map directly to step token when armed
_PHASE_STEP_TOKENS = frozenset(
    {"PLAN", "DECOMPOSE", "ANALYZE", "CREATIVE", "CLARIFY", "AUDIT", "QA", "BUGFIX", "DONE"}
)


@dataclass(frozen=True)
class Identity:
    """Resolved session identity."""

    role: str
    phase: str
    step: str
    epic_id: str
    command: str


@dataclass(frozen=True)
class Drift:
    """Diagnostic when session identity resolution detects drift or conflict."""

    code: Literal["phase_mismatch", "epic_mismatch", "step_unknown_while_armed"]
    armed_step: str
    ac_mode: str
    projection_phase: str
    epic_id: str
    role: str
    diagnostic_code: str = "CONTEXT_IDENTITY_DRIFT"


def resolve_session_identity(
    state: Any | None,
    ac_meta: Any | None,
    projection: dict[str, Any] | None = None,
) -> Identity | Drift:
    """Single typed resolver: resolve_session_identity(state, ac_meta, projection) -> Identity | Drift.

    Drift codes: phase_mismatch, epic_mismatch, step_unknown_while_armed.
    Fails closed if projection.phase and state/ac_meta disagree (FR-020: do not pick silent winner).
    """
    proj = dict(projection or {})

    # Extract state fields
    state_phase = ""
    state_armed_step = ""
    state_epic_id = ""
    state_role = ""
    if state is not None:
        if isinstance(state, dict):
            state_phase = str(state.get("phase") or "").strip().upper()
            state_armed_step = str(state.get("armed_step") or state.get("armed_after_finish") or "").strip()
            state_epic_id = str(state.get("epic_id") or state.get("last_finished_epic") or "").strip()
            state_role = _canonical_role(state.get("role"), default="")
        else:
            state_phase = str(getattr(state, "phase", None) or "").strip().upper()
            state_armed_step = str(getattr(state, "armed_step", None) or getattr(state, "armed_after_finish", None) or "").strip()
            state_epic_id = str(getattr(state, "epic_id", None) or getattr(state, "last_finished_epic", None) or "").strip()
            state_role = _canonical_role(getattr(state, "role", None), default="")

    # Extract ac_meta fields
    ac_role = ""
    ac_mode = ""
    ac_epic_id = ""
    ac_step_id = ""
    if ac_meta is not None:
        if isinstance(ac_meta, dict):
            ac_role = _canonical_role(ac_meta.get("role"), default="")
            ac_mode = str(ac_meta.get("mode") or "").strip().upper()
            ac_epic_id = str(ac_meta.get("epic_id") or "").strip()
            ac_step_id = str(ac_meta.get("step_id") or "").strip()
        else:
            ac_role = _canonical_role(getattr(ac_meta, "role", None), default="")
            ac_mode = str(getattr(ac_meta, "mode", None) or "").strip().upper()
            ac_epic_id = str(getattr(ac_meta, "epic_id", None) or "").strip()
            ac_step_id = str(getattr(ac_meta, "step_id", None) or "").strip()

    # Extract projection fields
    proj_phase_raw = _projection_value(proj, "phase", "mode", "loop_phase")
    proj_role_raw = _projection_value(proj, "role")
    proj_step_raw = _projection_value(proj, "step", "next_step")
    proj_epic_raw = _projection_value(proj, "epic", "epic_id")

    proj_role, proj_phase = _command_parts(proj_phase_raw, fallback_role=proj_role_raw, fallback_phase=proj_phase_raw)

    # Check epic mismatch if both provided and non-empty
    epic_candidates = [e for e in (state_epic_id, ac_epic_id, proj_epic_raw) if e and e != "unknown"]
    if len(set(epic_candidates)) > 1:
        # Conflict in epic_id
        return Drift(
            code="epic_mismatch",
            armed_step=state_armed_step or ac_step_id or proj_step_raw,
            ac_mode=ac_mode,
            projection_phase=proj_phase,
            epic_id=ac_epic_id or state_epic_id or proj_epic_raw,
            role=ac_role or state_role or proj_role or "BACK",
        )

    epic_id = epic_candidates[0] if epic_candidates else ""

    # Phase candidates and comparisons
    # Compare state armed_step/phase vs projection.phase vs ac_mode
    effective_armed_phase = state_phase
    if not effective_armed_phase and state_armed_step:
        # If armed_step is e.g. s01 -> phase is IMPLEMENT, else phase token
        if re.match(r"^[se]\d+", state_armed_step, re.IGNORECASE):
            effective_armed_phase = "IMPLEMENT"
        elif state_armed_step.upper() in _PHASE_STEP_TOKENS:
            effective_armed_phase = state_armed_step.upper()

    # Normalize phase tokens (e.g. "BACK QA" -> "QA")
    def _norm_p(p: str) -> str:
        toks = p.strip().upper().split()
        if len(toks) > 1 and toks[0] in _ROLE_ALIASES:
            return " ".join(toks[1:])
        return p.strip().upper()

    phase_sources = []
    if proj_phase:
        phase_sources.append(("projection", _norm_p(proj_phase)))
    if effective_armed_phase:
        phase_sources.append(("state", _norm_p(effective_armed_phase)))
    if ac_mode:
        phase_sources.append(("ac_meta", _norm_p(ac_mode)))

    if len(phase_sources) >= 2:
        norm_phases = set(p[1] for p in phase_sources)
        if len(norm_phases) > 1:
            return Drift(
                code="phase_mismatch",
                armed_step=state_armed_step or ac_step_id or proj_step_raw,
                ac_mode=ac_mode,
                projection_phase=proj_phase,
                epic_id=epic_id,
                role=ac_role or state_role or proj_role or "BACK",
            )

    resolved_phase = _norm_p(proj_phase) if proj_phase else (_norm_p(effective_armed_phase) if effective_armed_phase else (_norm_p(ac_mode) if ac_mode else "IMPLEMENT"))
    resolved_role = ac_role or state_role or proj_role or "BACK"

    # Step fallback chain: projection.step -> state.armed_step -> ac_step_id -> state.phase -> empty
    # Never the string "unknown" if armed
    step_candidate = proj_step_raw or state_armed_step or ac_step_id
    if not step_candidate:
        if resolved_phase in _PHASE_STEP_TOKENS:
            step_candidate = resolved_phase
        elif not (state_armed_step or state_phase):
            # Unarmed IDE / test without armed state
            step_candidate = "s01"
        elif resolved_phase == "IMPLEMENT":
            # Armed IMPLEMENT without step -> step_unknown_while_armed
            return Drift(
                code="step_unknown_while_armed",
                armed_step="",
                ac_mode=ac_mode,
                projection_phase=proj_phase,
                epic_id=epic_id,
                role=resolved_role,
            )

    step = step_candidate or ""
    command = f"{resolved_role} {resolved_phase}"

    return Identity(
        role=resolved_role,
        phase=resolved_phase,
        step=step,
        epic_id=epic_id,
        command=command,
    )


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
    state: Any | None = None,
    ac_meta: Any | None = None,
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

    is_unarmed = not raw or str(raw).strip().upper() == "UNKNOWN" or (not fallback_role and not fallback_phase and not command and not fallback_command)

    if not is_unarmed:
        if not role and phase:
            role = _canonical_role(fallback_role, default="BACK")
        if not phase and role:
            phase = "IMPLEMENT"

    # Step fallback chain: projection.step -> state.armed_step -> phase
    step = _projection_value(projection, "step", "next_step")
    if not step and state is not None:
        if isinstance(state, dict):
            step = str(state.get("armed_step") or state.get("armed_after_finish") or "").strip()
        else:
            step = str(getattr(state, "armed_step", None) or getattr(state, "armed_after_finish", None) or "").strip()

    if not step and ac_meta is not None:
        if isinstance(ac_meta, dict):
            step = str(ac_meta.get("step_id") or "").strip()
        else:
            step = str(getattr(ac_meta, "step_id", None) or "").strip()

    if not step and phase:
        clean_phase = phase.strip().upper()
        if clean_phase in _PHASE_STEP_TOKENS:
            step = clean_phase

    if not step:
        step = "-" if is_unarmed else ("" if (role or phase) else "-")

    if is_unarmed:
        normalized_command = "UNKNOWN"
        role = role or "UNKNOWN"
        phase = phase or ""
        step = "-"
    elif role and phase:
        if phase.strip().upper() == "DONE":
            normalized_command = "DONE"
        else:
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
        step=step,
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


__all__ = [
    "PromptScope",
    "Identity",
    "Drift",
    "resolve_session_identity",
    "build_prompt_scope",
    "render_prompt_scope",
]
