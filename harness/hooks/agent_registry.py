#!/usr/bin/env python3
"""Safe discovery and validation for project custom-agent definitions."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml


_MAX_DEFINITION_BYTES = 64 * 1024
_MAX_FRONTMATTER_BYTES = 16 * 1024
_MAX_FRONTMATTER_LINES = 128
_MAX_DEFINITIONS = 256
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_ENV_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")
_MODEL_SUFFIXES = ("_MODEL_CHAT", "_MODEL_LOOP", "_MODEL", "_ENABLED")

_LEGACY_OVERLAYS = {
    "explorer": {
        "managed": True,
        "mode": "search",
        "requires_model": False,
        "default_loop": True,
        "default_chat": False,
        "verdict": "none",
        "allow_worktree": False,
    },
    "sunset-inventory": {
        "managed": True,
        "mode": "search",
        "requires_model": False,
        "default_loop": True,
        "default_chat": False,
        "verdict": "none",
        "allow_worktree": False,
    },
    "verify": {
        "managed": True,
        "mode": "gate",
        "requires_model": True,
        "default_loop": True,
        "default_chat": False,
        "verdict": "pass-fail",
        "allow_worktree": False,
    },
    "reviewer": {
        "managed": True,
        "mode": "gate",
        "requires_model": True,
        "default_loop": True,
        "default_chat": False,
        "verdict": "pass-blocked-fail",
        "allow_worktree": False,
    },
}


@dataclass(frozen=True)
class AgentOverlay:
    managed: bool = False
    mode: str = "optional"
    requires_model: bool = False
    default_loop: bool = False
    default_chat: bool = False
    verdict: str = "none"
    allow_worktree: bool = False
    max_runtime_sec: int | None = None


@dataclass(frozen=True)
class RegistryDiagnostic:
    code: str
    agent_id: str | None = None
    key: str | None = None


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    filename: str
    description: str = ""
    tools: str | tuple[str, ...] | None = None
    disallowed_tools: str | tuple[str, ...] | None = None
    overlay: AgentOverlay = AgentOverlay()
    model: str | None = None
    model_source: str | None = None
    chat_enabled: bool = False
    loop_enabled: bool = False
    runnable: bool = False

    @property
    def managed(self) -> bool:
        return self.overlay.managed

    @property
    def mode(self) -> str:
        return self.overlay.mode

    @property
    def verdict(self) -> str:
        return self.overlay.verdict


@dataclass(frozen=True)
class AgentRegistry:
    project_root: Path
    agents: tuple[AgentDefinition, ...]
    diagnostics: tuple[RegistryDiagnostic, ...]
    revision: str

    @property
    def definitions(self) -> tuple[AgentDefinition, ...]:
        return self.agents

    @property
    def by_id(self) -> dict[str, AgentDefinition]:
        return {agent.id: agent for agent in self.agents}

    @property
    def errors(self) -> tuple[RegistryDiagnostic, ...]:
        return self.diagnostics

    def get(self, agent_id: str) -> AgentDefinition | None:
        target = resolve_agent_alias(agent_id)
        res = self.by_id.get(_normalize_id(target))
        if res is not None:
            return res
        norm = _normalize_id(agent_id)
        if norm is not None:
            res = self.by_id.get(norm)
            if res is not None:
                return res
            for alias, canonical in AGENT_ALIASES.items():
                if canonical == norm and alias in self.by_id:
                    return self.by_id[alias]
        return None


def resolve_project_root(
    project_dir: str | Path | None = None,
    environ: Mapping[str, object] | None = None,
) -> Path:
    """Resolve a project root without reading runtime state or executing config."""
    env = os.environ if environ is None else environ
    candidate = project_dir or env.get("CLAUDE_PROJECT_DIR") or Path.cwd()
    return Path(str(candidate)).expanduser().resolve(strict=False)


def _normalize_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if _NAME_RE.fullmatch(normalized) else None


AGENT_ALIASES: dict[str, str] = {
    "sunset": "sunset-inventory",
    "verify": "verify-implement",
    "reviewer": "verify-qa",
}


def resolve_agent_alias(name: str) -> str:
    """Resolve agent alias if registered, otherwise return original name normalized."""
    normalized = _normalize_id(name) or name
    return AGENT_ALIASES.get(normalized, normalized)


def _env_token(agent_id: str) -> str:
    return agent_id.upper().replace("-", "_")


def _model_valid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value == "inherit":
        return value
    if not _MODEL_RE.fullmatch(value) or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    return value


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    return {"1": True, "true": True, "yes": True, "on": True, "0": False, "false": False, "no": False, "off": False}.get(value.strip().lower())


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines()[:2048]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        try:
            parts = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            continue
        values[key] = parts[0] if parts else ""
    return values


def _read_frontmatter(path: Path) -> tuple[dict[str, object] | None, str | None]:
    try:
        raw = path.read_bytes()
    except OSError:
        return None, "definition_unreadable"
    if len(raw) > _MAX_DEFINITION_BYTES:
        return None, "definition_too_large"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "definition_invalid"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "frontmatter_missing"
    closing = next((index for index, line in enumerate(lines[1:], 1) if line.strip() in {"---", "..."}), None)
    if closing is None:
        return None, "frontmatter_unbounded"
    frontmatter = "\n".join(lines[1:closing])
    if len(frontmatter.encode("utf-8")) > _MAX_FRONTMATTER_BYTES or closing > _MAX_FRONTMATTER_LINES:
        return None, "frontmatter_too_large"
    try:
        parsed = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError:
        return None, "definition_invalid"
    if not isinstance(parsed, dict):
        return None, "definition_invalid"
    return parsed, None


def _legacy_or_default(agent_id: str, metadata: object) -> tuple[AgentOverlay | None, str | None]:
    if metadata is None and agent_id in _LEGACY_OVERLAYS:
        metadata = _LEGACY_OVERLAYS[agent_id]
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        return None, "overlay_invalid"
    allowed = {"managed", "mode", "requires_model", "default_loop", "default_chat", "verdict", "allow_worktree", "max_runtime_sec"}
    if set(metadata) - allowed:
        return None, "overlay_field_invalid"
    legacy = _LEGACY_OVERLAYS.get(agent_id, {})
    managed = metadata.get("managed", legacy.get("managed", False))
    mode = metadata.get("mode", legacy.get("mode", "optional"))
    requires_model = metadata.get("requires_model", legacy.get("requires_model", bool(managed)))
    default_loop = metadata.get("default_loop", legacy.get("default_loop", bool(managed)))
    default_chat = metadata.get("default_chat", legacy.get("default_chat", False))
    verdict = metadata.get("verdict", legacy.get("verdict", "none"))
    allow_worktree = metadata.get("allow_worktree", legacy.get("allow_worktree", False))
    max_runtime_sec = metadata.get("max_runtime_sec")
    if not all(isinstance(value, bool) for value in (managed, requires_model, default_loop, default_chat, allow_worktree)):
        return None, "overlay_field_invalid"
    if mode not in {"gate", "optional", "search", "repair"} or verdict not in {"pass-fail", "pass-blocked-fail", "none"}:
        return None, "overlay_field_invalid"
    if max_runtime_sec is not None and (isinstance(max_runtime_sec, bool) or not isinstance(max_runtime_sec, int) or max_runtime_sec <= 0):
        return None, "overlay_field_invalid"
    return AgentOverlay(managed, mode, requires_model, default_loop, default_chat, verdict, allow_worktree, max_runtime_sec), None


def _env_entries(*layers: Mapping[str, object]) -> dict[str, tuple[str, object]]:
    entries: dict[str, tuple[str, object]] = {}
    suffixes = sorted(_MODEL_SUFFIXES, key=len, reverse=True)
    for source, layer in zip(("process", "project.env.local", "project.env"), layers):
        for raw_key, value in layer.items():
            key = str(raw_key)
            if not key.startswith("PROJECT_AGENT_"):
                continue
            rest = key.removeprefix("PROJECT_AGENT_")
            for suffix in suffixes:
                if not rest.endswith(suffix):
                    continue
                token = rest[: -len(suffix)]
                if _ENV_TOKEN_RE.fullmatch(token):
                    entries.setdefault(key, (source, value))
                break
    return entries


def _load_layers(root: Path, process_env: Mapping[str, object] | None, project_env_local: Mapping[str, object] | None, project_env: Mapping[str, object] | None) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    return (
        dict(os.environ) if process_env is None else process_env,
        _parse_dotenv(root / ".claude" / "project.env.local") if project_env_local is None else project_env_local,
        _parse_dotenv(root / ".claude" / "project.env") if project_env is None else project_env,
    )


def discover_registry(
    project_dir: str | Path | None = None,
    *,
    process_env: Mapping[str, object] | None = None,
    project_env_local: Mapping[str, object] | None = None,
    project_env: Mapping[str, object] | None = None,
) -> AgentRegistry:
    """Discover bounded agent definitions and resolve only matching project keys."""
    root = resolve_project_root(project_dir, process_env)
    process, local, project = _load_layers(root, process_env, project_env_local, project_env)
    entries = _env_entries(process, local, project)
    diagnostics: list[RegistryDiagnostic] = []
    agents_dir = root / ".claude" / "agents"
    paths = sorted(agents_dir.glob("*.md"), key=lambda path: path.name) if agents_dir.is_dir() else []
    harness_dir = root / "harness" / "agents"
    if harness_dir.is_dir():
        seen_stems = {p.stem.lower() for p in paths}
        for harness_path in sorted(harness_dir.glob("*.md"), key=lambda path: path.name):
            stem = harness_path.stem.lower()
            if stem not in seen_stems:
                paths.append(harness_path)
                seen_stems.add(stem)
    paths = sorted(paths, key=lambda path: path.name)
    if len(paths) > _MAX_DEFINITIONS:
        paths = paths[:_MAX_DEFINITIONS]
        diagnostics.append(RegistryDiagnostic("definitions_truncated"))

    parsed: list[tuple[Path, str, dict[str, object], AgentOverlay]] = []
    for path in paths:
        metadata, error = _read_frontmatter(path)
        if error:
            diagnostics.append(RegistryDiagnostic(error, path.stem.lower()))
            continue
        assert metadata is not None
        agent_id = _normalize_id(metadata.get("name"))
        if agent_id is None:
            diagnostics.append(RegistryDiagnostic("definition_invalid", path.stem.lower()))
            continue
        filename_id = _normalize_id(path.stem)
        if filename_id != agent_id:
            diagnostics.append(RegistryDiagnostic("filename_mismatch", agent_id))
            if filename_id is None or filename_id.replace("-", "_") != agent_id.replace("-", "_"):
                diagnostics.append(RegistryDiagnostic("definition_invalid", agent_id))
                continue
        overlay, overlay_error = _legacy_or_default(agent_id, metadata.get("overlay"))
        if overlay_error:
            diagnostics.append(RegistryDiagnostic("definition_invalid", agent_id))
            continue
        assert overlay is not None
        parsed.append((path, agent_id, metadata, overlay))

    counts: dict[str, int] = {}
    for _, agent_id, _, _ in parsed:
        counts[agent_id] = counts.get(agent_id, 0) + 1
    duplicate_ids = {agent_id for agent_id, count in counts.items() if count > 1}
    for agent_id in sorted(duplicate_ids):
        diagnostics.append(RegistryDiagnostic("duplicate_agent_id", agent_id))

    definitions: list[AgentDefinition] = []
    known_tokens = {_env_token(agent_id): agent_id for _, agent_id, _, _ in parsed if agent_id not in duplicate_ids}
    for path, agent_id, metadata, overlay in parsed:
        if agent_id in duplicate_ids:
            continue
        token = _env_token(agent_id)
        matching = {key: item for key, item in entries.items() if key.removeprefix("PROJECT_AGENT_").startswith(token) and (key.removeprefix("PROJECT_AGENT_")[len(token):].startswith("_MODEL") or key.removeprefix("PROJECT_AGENT_")[len(token):] == "_ENABLED")}
        model_key = f"PROJECT_AGENT_{token}_MODEL"
        model_entry = matching.get(model_key)
        model: str | None = None
        model_source: str | None = None
        config_error = False
        if model_entry is not None:
            model_source, raw_model = model_entry
            model = _model_valid(raw_model)
            if model is None:
                diagnostics.append(RegistryDiagnostic("model_invalid", agent_id, model_key))
                config_error = True
            elif model == "inherit":
                model = None
        if overlay.managed and overlay.requires_model and model_entry is None:
            diagnostics.append(RegistryDiagnostic("model_missing", agent_id, model_key))
            config_error = True
        if not overlay.managed:
            chat_enabled = loop_enabled = False
            runnable = True
        else:
            chat_key = f"PROJECT_AGENT_{token}_MODEL_CHAT"
            loop_key = f"PROJECT_AGENT_{token}_MODEL_LOOP"
            enabled_key = f"PROJECT_AGENT_{token}_ENABLED"
            chat_value = matching.get(chat_key, matching.get(enabled_key, (None, overlay.default_chat)))[1]
            loop_value = matching.get(loop_key, matching.get(enabled_key, (None, overlay.default_loop)))[1]
            chat_enabled = _parse_bool(chat_value)
            loop_enabled = _parse_bool(loop_value)
            if chat_enabled is None:
                diagnostics.append(RegistryDiagnostic("scope_invalid_chat", agent_id, chat_key))
                config_error = True
                chat_enabled = False
            if loop_enabled is None:
                diagnostics.append(RegistryDiagnostic("scope_invalid_loop", agent_id, loop_key))
                config_error = True
                loop_enabled = False
            if enabled_key in matching and chat_key not in matching and loop_key not in matching and _parse_bool(matching[enabled_key][1]) is None:
                diagnostics.append(RegistryDiagnostic("invalid_enabled", agent_id, enabled_key))
                config_error = True
            runnable = not config_error  # Explicit inherit is valid; missing/invalid models set config_error above.
        description = metadata.get("description", "")
        if not isinstance(description, str):
            diagnostics.append(RegistryDiagnostic("definition_invalid", agent_id))
            continue
        definitions.append(AgentDefinition(agent_id, path.name, description, metadata.get("tools"), metadata.get("disallowedTools"), overlay, model, model_source, bool(chat_enabled), bool(loop_enabled), runnable))

    definition_ids = {agent.id for agent in definitions}
    for key in entries:
        rest = key.removeprefix("PROJECT_AGENT_")
        token = next((rest[: -len(suffix)] for suffix in _MODEL_SUFFIXES if rest.endswith(suffix)), None)
        if token and token in known_tokens and known_tokens[token] in definition_ids:
            continue
        if token and (key.endswith("_MODEL") or key.endswith("_MODEL_CHAT") or key.endswith("_MODEL_LOOP")):
            diagnostics.append(RegistryDiagnostic("orphan_env", token.lower(), key))

    normalized = []
    for agent in sorted(definitions, key=lambda item: item.id):
        normalized.append({"id": agent.id, "file": agent.filename, "overlay": agent.overlay.__dict__ if hasattr(agent.overlay, "__dict__") else {field: getattr(agent.overlay, field) for field in AgentOverlay.__dataclass_fields__}, "model_source": agent.model_source, "model": hashlib.sha256((agent.model or "inherit").encode()).hexdigest()[:12], "chat": agent.chat_enabled, "loop": agent.loop_enabled, "runnable": agent.runnable})
    revision = "sha256:" + hashlib.sha256(json.dumps(normalized + [{"code": diagnostic.code, "agent_id": diagnostic.agent_id, "key": diagnostic.key} for diagnostic in diagnostics], sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    return AgentRegistry(root, tuple(sorted(definitions, key=lambda item: item.id)), tuple(diagnostics), revision)


def discover_agent_registry(*args, **kwargs) -> AgentRegistry:
    return discover_registry(*args, **kwargs)


load_registry = discover_registry

__all__ = [
    "AGENT_ALIASES",
    "AgentDefinition",
    "AgentOverlay",
    "AgentRegistry",
    "RegistryDiagnostic",
    "discover_agent_registry",
    "discover_registry",
    "load_registry",
    "resolve_agent_alias",
    "resolve_project_root",
]
