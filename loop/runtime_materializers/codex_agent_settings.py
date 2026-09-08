"""Codex-native settings for generated custom subagents."""
from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any


class CodexAgentSettingsError(ValueError):
    pass


_NATIVE_FIELDS = frozenset({"model", "model_reasoning_effort", "sandbox_mode"})
_WORKFLOW_FIELDS = frozenset(
    {"workflow_mode", "max_turns", "requires_model", "allow_worktree", "verdict"}
)
_DEFAULT_FIELDS = _NATIVE_FIELDS | frozenset(
    {"max_concurrent_threads_per_session", "max_depth"}
)
_REASONING = frozenset({"low", "medium", "high", "xhigh"})
_SANDBOX = frozenset({"read-only", "workspace-write", "danger-full-access"})
_WORKFLOW_MODES = frozenset({"gate", "search", "repair", "implement"})


def _ensure_string(data: dict[str, Any], key: str, owner: str) -> None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise CodexAgentSettingsError(f"{owner}.{key} must be a string")


def _validate_agent_table(data: dict[str, Any], owner: str) -> None:
    unknown = sorted(set(data) - _NATIVE_FIELDS - _WORKFLOW_FIELDS)
    if unknown:
        raise CodexAgentSettingsError(
            f"{owner} contains unsupported Codex agent settings: {unknown}"
        )
    _ensure_string(data, "model", owner)
    _ensure_string(data, "model_reasoning_effort", owner)
    _ensure_string(data, "sandbox_mode", owner)
    effort = data.get("model_reasoning_effort")
    if effort is not None and effort not in _REASONING:
        raise CodexAgentSettingsError(
            f"{owner}.model_reasoning_effort must be one of {sorted(_REASONING)}"
        )
    sandbox = data.get("sandbox_mode")
    if sandbox is not None and sandbox not in _SANDBOX:
        raise CodexAgentSettingsError(
            f"{owner}.sandbox_mode must be one of {sorted(_SANDBOX)}"
        )
    mode = data.get("workflow_mode")
    if mode is not None and mode not in _WORKFLOW_MODES:
        raise CodexAgentSettingsError(
            f"{owner}.workflow_mode must be one of {sorted(_WORKFLOW_MODES)}"
        )
    if "max_turns" in data and (
        not isinstance(data["max_turns"], int) or data["max_turns"] <= 0
    ):
        raise CodexAgentSettingsError(f"{owner}.max_turns must be a positive integer")
    for key in ("requires_model", "allow_worktree"):
        if key in data and not isinstance(data[key], bool):
            raise CodexAgentSettingsError(f"{owner}.{key} must be a boolean")
    if "verdict" in data and not isinstance(data["verdict"], str):
        raise CodexAgentSettingsError(f"{owner}.verdict must be a string")


def load_codex_agent_settings(
    repo_root: str | Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = Path(repo_root) / "codex" / "agents.config.toml"
    if not path.is_file():
        return {}, {}
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CodexAgentSettingsError(f"cannot read {path}: {exc}") from exc

    if raw.get("schema_version") != "codex-agent-settings/v1":
        raise CodexAgentSettingsError(
            f"{path} must declare schema_version = 'codex-agent-settings/v1'"
        )
    defaults = raw.get("defaults", {})
    agents = raw.get("agents", {})
    if not isinstance(defaults, dict) or not isinstance(agents, dict):
        raise CodexAgentSettingsError(f"{path} defaults and agents must be tables")
    unknown_defaults = sorted(set(defaults) - _DEFAULT_FIELDS)
    if unknown_defaults:
        raise CodexAgentSettingsError(
            f"defaults contains unsupported settings: {unknown_defaults}"
        )
    _validate_agent_table(
        {
            key: value
            for key, value in defaults.items()
            if key not in {"max_concurrent_threads_per_session", "max_depth"}
        },
        "defaults",
    )
    for key in ("max_concurrent_threads_per_session", "max_depth"):
        if key in defaults and (
            not isinstance(defaults[key], int) or defaults[key] <= 0
        ):
            raise CodexAgentSettingsError(f"defaults.{key} must be a positive integer")

    normalized_agents: dict[str, dict[str, Any]] = {}
    for name, settings in agents.items():
        if not isinstance(name, str) or not name.strip():
            raise CodexAgentSettingsError("agents keys must be non-empty strings")
        if not isinstance(settings, dict):
            raise CodexAgentSettingsError(f"agents.{name} must be a table")
        _validate_agent_table(settings, f"agents.{name}")
        normalized_agents[name] = dict(settings)
    return dict(defaults), normalized_agents


def resolve_codex_agent_settings(
    repo_root: str | Path,
    agent_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults, agents = load_codex_agent_settings(repo_root)
    resolved = {key: value for key, value in defaults.items() if key in _NATIVE_FIELDS}
    agent = agents.get(agent_name, {})
    resolved.update({key: value for key, value in agent.items() if key in _NATIVE_FIELDS})
    workflow = {key: value for key, value in agent.items() if key in _WORKFLOW_FIELDS}
    return resolved, workflow


def validate_codex_workflow_settings(
    workflow: dict[str, Any],
    policy: dict[str, Any],
    agent_name: str,
) -> None:
    pairs = {
        "workflow_mode": policy.get("mode"),
        "max_turns": policy.get("maxTurns"),
        "requires_model": policy.get("requires_model"),
        "allow_worktree": policy.get("allow_worktree"),
        "verdict": policy.get("verdict"),
    }
    for key, expected in pairs.items():
        if key in workflow and expected is not None and workflow[key] != expected:
            raise CodexAgentSettingsError(
                f"agents.{agent_name}.{key}={workflow[key]!r} conflicts with "
                f"harness policy {expected!r}"
            )
