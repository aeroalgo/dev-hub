#!/usr/bin/env python3
"""Pure per-agent policy resolution for chat and loop contexts."""
from __future__ import annotations

import os
import re
from enum import Enum
from typing import Mapping


class AgentContext(str, Enum):
    CHAT = "chat"
    LOOP = "loop"


class PolicyReason(str, Enum):
    EXPLICIT_SELECTOR = "explicit_selector"
    METADATA = "metadata"
    COMPATIBILITY = "compatibility"
    LEGACY_DEFAULT = "legacy_default"
    INHERIT = "inherit"


class PolicyErrorCode(str, Enum):
    AGENT_INVALID = "agent_invalid"
    SCOPE_INVALID = "scope_invalid"
    BOOLEAN_INVALID = "boolean_invalid"
    MODEL_INVALID = "model_invalid"


MODEL_ALIASES: dict[str, str] = {
    "fable": "fable",
    "haiku": "haiku",
    "opus": "opus",
    "sonnet": "sonnet",
}

_AGENT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_BOOLEAN_VALUES = {
    "1": True,
    "true": True,
    "yes": True,
    "on": True,
    "0": False,
    "false": False,
    "no": False,
    "off": False,
}


class AgentResolvedPolicy:
    __slots__ = ("agent", "context", "enabled", "model", "reason", "error", "source")

    def __init__(
        self,
        agent: str,
        context: AgentContext | str,
        *,
        enabled: bool = False,
        model: str | None = None,
        reason: PolicyReason | None = None,
        error: PolicyErrorCode | None = None,
        source: str | None = None,
    ) -> None:
        self.agent = agent
        self.context = context
        self.enabled = enabled
        self.model = model
        self.reason = reason
        self.error = error
        self.source = source

    def __repr__(self) -> str:
        return (
            f"AgentResolvedPolicy(agent={self.agent!r}, context={self.context!r}, "
            f"enabled={self.enabled!r}, model={self.model!r}, reason={self.reason!r}, "
            f"error={self.error!r}, source={self.source!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AgentResolvedPolicy):
            return NotImplemented
        return all(
            getattr(self, field) == getattr(other, field) for field in self.__slots__
        )

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, field) for field in self.__slots__))


def _failure(
    agent: str,
    context: AgentContext | str,
    error: PolicyErrorCode,
) -> AgentResolvedPolicy:
    return AgentResolvedPolicy(agent, context, error=error)


def _context(value: AgentContext | str) -> AgentContext | None:
    if isinstance(value, AgentContext):
        return value
    try:
        return AgentContext(str(value).strip().lower())
    except ValueError:
        return None


def _parse_bool(value: object) -> bool | None:
    if not isinstance(value, str):
        return None
    return _BOOLEAN_VALUES.get(value.strip().lower())


def _valid_model(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized == "inherit":
        return "inherit"
    if normalized in MODEL_ALIASES:
        return MODEL_ALIASES[normalized]
    if _MODEL_RE.fullmatch(normalized):
        return normalized
    return None


def _first_value(
    key: str,
    env: Mapping[str, object],
    project_env_local: Mapping[str, object],
    project_env: Mapping[str, object],
    metadata: Mapping[str, object],
    compatibility: Mapping[str, object],
) -> tuple[object, str] | None:
    for values, source in (
        (env, "process"),
        (project_env_local, "project.env.local"),
        (project_env, "project.env"),
        (metadata, "metadata"),
        (compatibility, "compatibility"),
    ):
        if key in values:
            return values[key], source
    return None


def resolve_agent_policy(
    agent: str,
    context: AgentContext | str,
    *,
    env: Mapping[str, object] | None = None,
    project_env_local: Mapping[str, object] | None = None,
    project_env: Mapping[str, object] | None = None,
    metadata: Mapping[str, object] | None = None,
    compatibility: Mapping[str, object] | None = None,
) -> AgentResolvedPolicy:
    """Resolve one agent/context without workflow or EPIC_LOOP side effects.

    Scope selectors: PROJECT_AGENT_<NAME>_MODEL_{CHAT|LOOP} are booleans only.
    Model: PROJECT_AGENT_<NAME>_MODEL only (never *_MODEL_CHAT / *_MODEL_LOOP).
    Absent selector → loop=1, chat=0 (LEGACY_DEFAULT).
    """
    normalized_agent = agent.strip().lower() if isinstance(agent, str) else ""
    if not _AGENT_RE.fullmatch(normalized_agent):
        return _failure(normalized_agent, context, PolicyErrorCode.AGENT_INVALID)
    resolved_context = _context(context)
    if resolved_context is None:
        return _failure(normalized_agent, context, PolicyErrorCode.SCOPE_INVALID)

    process = env if env is not None else os.environ
    local = project_env_local or {}
    project = project_env or {}
    meta = metadata or {}
    compat = compatibility or {}
    prefix = f"PROJECT_AGENT_{normalized_agent.upper()}"
    scope = resolved_context.value.upper()

    enabled_value = _first_value(
        f"{prefix}_MODEL_{scope}", process, local, project, {}, {}
    )
    reason: PolicyReason | None = (
        PolicyReason.EXPLICIT_SELECTOR if enabled_value is not None else None
    )
    if enabled_value is None:
        enabled_value = _first_value(
            "enabled_" + resolved_context.value,
            {},
            {},
            {},
            meta,
            compat,
        )
        if enabled_value is not None:
            reason = (
                PolicyReason.METADATA
                if enabled_value[1] == "metadata"
                else PolicyReason.COMPATIBILITY
            )
    if enabled_value is None:
        enabled_value = _first_value("enabled", {}, {}, {}, {}, compat)
        if enabled_value is not None:
            reason = PolicyReason.COMPATIBILITY

    if enabled_value is None:
        enabled = resolved_context is AgentContext.LOOP
        reason = PolicyReason.LEGACY_DEFAULT
        enabled_source = None
    else:
        parsed_enabled = _parse_bool(enabled_value[0])
        if parsed_enabled is None:
            return _failure(
                normalized_agent, resolved_context, PolicyErrorCode.BOOLEAN_INVALID
            )
        enabled = parsed_enabled
        if reason is None:
            reason = PolicyReason.EXPLICIT_SELECTOR
        enabled_source = enabled_value[1]

    model_value = _first_value(
        f"{prefix}_MODEL", process, local, project, {}, {}
    )
    if model_value is None:
        model_value = _first_value("model", {}, {}, {}, meta, compat)

    model: str | None = None
    source = enabled_source
    if model_value is not None:
        model = _valid_model(model_value[0])
        if model is None:
            return _failure(
                normalized_agent, resolved_context, PolicyErrorCode.MODEL_INVALID
            )
        source = model_value[1]
        if model == "inherit":
            model = None
            reason = PolicyReason.INHERIT

    return AgentResolvedPolicy(
        normalized_agent,
        resolved_context,
        enabled=enabled,
        model=model,
        reason=reason,
        source=source,
    )


def agent_names_from_env(*layers: Mapping[str, object]) -> set[str]:
    """Return safe agent names represented by policy environment keys."""
    names: set[str] = set()
    pattern = re.compile(
        r"^PROJECT_AGENT_([A-Z][A-Z0-9_-]*?)(?:_MODEL(?:_CHAT|_LOOP)?|_ENABLED)?$"
    )
    for layer in layers:
        for key in layer:
            match = pattern.fullmatch(str(key))
            if match:
                name = match.group(1).lower()
                if _AGENT_RE.fullmatch(name) and name not in {"enabled", "model"}:
                    names.add(name)
    return names
