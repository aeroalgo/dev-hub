from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
import yaml
from pydantic import BaseModel, Field, ValidationError

from loop.board_projection.errors import ProjectionConfigError

DEFAULT_CONFIG_PATH = Path(".loop/board-projection.yaml")
ENV_CONFIG_PATH_VAR = "LOOP_BOARD_PROJECTION_CONFIG"
ENV_BOARD_PROVIDER = "LOOP_BOARD_PROVIDER"
ENV_BITRIX_WEBHOOK_URL = "BITRIX_WEBHOOK_URL"
ENV_BITRIX_GROUP_ID = "BITRIX_GROUP_ID"
ENV_BITRIX_RESPONSIBLE_ID = "BITRIX_RESPONSIBLE_ID"
ENV_BITRIX_STAGE_MAP = "BITRIX_STAGE_MAP"
ENV_PLANE_API_KEY = "PLANE_API_KEY"
ENV_PLANE_BASE_URL = "PLANE_BASE_URL"
ENV_PLANE_WORKSPACE_SLUG = "PLANE_WORKSPACE_SLUG"
ENV_PLANE_PROJECT_ID = "PLANE_PROJECT_ID"
ENV_PLANE_STATE_MAP = "PLANE_STATE_MAP"
ENV_PROJECT_DOCS_FOLDER = "PROJECT_DOCS_FOLDER"

SUPPORTED_PROVIDERS = {"none", "bitrix24", "plane"}
STAGE_ALIASES = ("backlog", "design", "build", "verify", "uat", "done", "blocked")

DEFAULT_PHASE_ALIASES: dict[str, str] = {
    "QUEUED": "backlog",
    "PLAN": "design",
    "CLARIFY": "design",
    "DECOMPOSE": "design",
    "ANALYZE": "design",
    "CREATIVE": "design",
    "IMPLEMENT": "build",
    "SECURITY": "build",
    "AUDIT": "build",
    "QA": "verify",
    "BUGFIX": "verify",
    "CONTEXT_SYNC": "uat",
    "DONE": "done",
    "HALT": "blocked",
}

_BOARD_ENV_KEYS = frozenset(
    {
        "LOOP_BOARD_PROVIDER",
        "BITRIX_WEBHOOK_URL",
        "BITRIX_GROUP_ID",
        "BITRIX_RESPONSIBLE_ID",
        "BITRIX_STAGE_MAP",
        "PLANE_API_KEY",
        "PLANE_BASE_URL",
        "PLANE_WORKSPACE_SLUG",
        "PLANE_PROJECT_ID",
        "PLANE_STATE_MAP",
        "PROJECT_DOCS_FOLDER",
        *{f"BITRIX_STAGE_{alias.upper()}" for alias in STAGE_ALIASES},
        *{f"PLANE_STATE_{alias.upper()}" for alias in STAGE_ALIASES},
    }
)


def _load_board_env_from_files(project_root: Path) -> dict[str, str]:
    """Load project board settings without mutating the process environment.

    LoopSettings already reads these dotenv files for loop configuration, but
    unknown settings are intentionally ignored and therefore are not exported
    to ``os.environ``. Board projection reads its own provider settings from the
    environment, so load only the board-related keys here. Existing process
    environment values keep precedence over dotenv files.
    """
    candidates: list[Path] = []
    dev_hub = (os.environ.get("DEV_HUB") or "").strip()
    if dev_hub:
        candidates.append(Path(dev_hub).expanduser() / ".env")
    candidates.append(project_root / ".env")

    values: dict[str, str] = {
        key: os.environ[key]
        for key in _BOARD_ENV_KEYS
        if key in os.environ
    }
    explicit_env_keys = set(values)
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        try:
            parsed = dotenv_values(candidate)
        except (OSError, UnicodeError):
            continue
        for key, value in parsed.items():
            if key in _BOARD_ENV_KEYS and value is not None and key not in explicit_env_keys:
                values[key] = str(value)

    return values


class Bitrix24Config(BaseModel):
    webhook_url: str = Field(default="", description="Inbound webhook REST endpoint")
    group_id: int | None = Field(default=None, description="Project / Sonet group ID")
    responsible_id: int | None = Field(
        default=None,
        description="Bitrix24 user ID for RESPONSIBLE_ID (required by tasks.task.add)",
    )
    stage_map: dict[str, str] = Field(default_factory=dict, description="Mapping alias -> stageId")

    def is_complete(self) -> bool:
        return bool(
            self.webhook_url
            and self.group_id is not None
            and self.responsible_id is not None
        )


class PlaneConfig(BaseModel):
    base_url: str = Field(default="", description="Plane instance base URL")
    api_key: str = Field(default="", description="Plane API token")
    workspace_slug: str = Field(default="", description="Plane workspace slug")
    project_id: str = Field(default="", description="Plane project ID")
    state_map: dict[str, str] = Field(default_factory=dict, description="Mapping alias -> state_id")

    def is_complete(self) -> bool:
        return bool(self.base_url and self.api_key and self.workspace_slug and self.project_id)


class ProvidersConfig(BaseModel):
    bitrix24: Bitrix24Config = Field(default_factory=Bitrix24Config)
    plane: PlaneConfig = Field(default_factory=PlaneConfig)


class ProjectDocFile(BaseModel):
    model_config = {"populate_by_name": True}

    path: str = Field(description="Repo-relative path to a documentation file")
    as_name: str | None = Field(
        default=None,
        alias="as",
        description="Optional remote filename override",
    )


class ProjectDocsConfig(BaseModel):
    folder_name: str = Field(
        default="docs",
        description="Bitrix Disk folder (under group) / Plane docs namespace label",
    )
    files: list[ProjectDocFile] = Field(
        default_factory=list,
        description="Curated project docs (workflow/gitflow/runbooks), not epic cards",
    )


class BoardProjectionConfig(BaseModel):
    schema_version: str = Field(default="loop-board-projection/v1", alias="schema")
    provider: str = Field(default="none")
    role_allowlist: list[str] = Field(default_factory=lambda: ["back"])
    phase_alias: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_PHASE_ALIASES))
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    project_docs: ProjectDocsConfig = Field(default_factory=ProjectDocsConfig)

    def is_role_allowed(self, role: str | None) -> bool:
        if not role:
            return False
        return role.strip().lower() in {r.strip().lower() for r in self.role_allowlist}

    def check_provider_completeness(self) -> tuple[bool, str | None]:
        if self.provider == "none":
            return True, None
        if self.provider == "bitrix24":
            if not self.providers.bitrix24.is_complete():
                return False, "incomplete_provider_config"
            return True, None
        if self.provider == "plane":
            if not self.providers.plane.is_complete():
                return False, "incomplete_provider_config"
            return True, None
        return False, f"unsupported_provider_{self.provider}"


def resolve_config_path(explicit_path: Path | str | None = None) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    env_override = os.environ.get(ENV_CONFIG_PATH_VAR)
    if env_override:
        return Path(env_override)
    return DEFAULT_CONFIG_PATH


def _env_str(name: str, env: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if env is None else env
    value = (source.get(name) or "").strip()
    return value or None


def _env_int(name: str, env: Mapping[str, str] | None = None) -> int | None:
    raw = _env_str(name, env)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ProjectionConfigError(f"Invalid integer in env {name}={raw!r}") from exc


def _parse_json_map(name: str, env: Mapping[str, str] | None = None) -> dict[str, str] | None:
    raw = _env_str(name, env)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProjectionConfigError(f"Invalid JSON object in env {name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectionConfigError(f"Env {name} must be a JSON object of string keys/values")
    out: dict[str, str] = {}
    for key, value in data.items():
        if value is None or value == "":
            continue
        out[str(key)] = str(value)
    return out


def _alias_map_from_env(prefix: str, env: Mapping[str, str] | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for alias in STAGE_ALIASES:
        value = _env_str(f"{prefix}{alias.upper()}", env)
        if value is not None:
            out[alias] = value
    return out


def apply_env_overrides(
    config: BoardProjectionConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> BoardProjectionConfig:
    """
    Per-project board identity comes from env (each repo/board differs).
    Env wins over YAML for provider, Bitrix/Plane ids/maps, docs folder, secrets.
    YAML keeps shared structure: phase_alias, role_allowlist, project_docs.files.
    """
    bitrix = config.providers.bitrix24
    plane = config.providers.plane
    docs = config.project_docs

    provider = (_env_str(ENV_BOARD_PROVIDER, env) or config.provider or "none").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ProjectionConfigError(
            f"Unknown board projection provider from env/yaml: '{provider}'. Supported: {SUPPORTED_PROVIDERS}"
        )

    webhook = _env_str(ENV_BITRIX_WEBHOOK_URL, env) or bitrix.webhook_url
    group_id = _env_int(ENV_BITRIX_GROUP_ID, env)
    if group_id is None:
        group_id = bitrix.group_id
    responsible_id = _env_int(ENV_BITRIX_RESPONSIBLE_ID, env)
    if responsible_id is None:
        responsible_id = bitrix.responsible_id

    stage_map = dict(bitrix.stage_map)
    stage_map.update(_alias_map_from_env("BITRIX_STAGE_", env))
    json_stages = _parse_json_map(ENV_BITRIX_STAGE_MAP, env)
    if json_stages:
        stage_map.update(json_stages)

    api_key = _env_str(ENV_PLANE_API_KEY, env) or plane.api_key
    base_url = _env_str(ENV_PLANE_BASE_URL, env) or plane.base_url
    workspace_slug = _env_str(ENV_PLANE_WORKSPACE_SLUG, env) or plane.workspace_slug
    project_id = _env_str(ENV_PLANE_PROJECT_ID, env) or plane.project_id

    state_map = dict(plane.state_map)
    state_map.update(_alias_map_from_env("PLANE_STATE_", env))
    json_states = _parse_json_map(ENV_PLANE_STATE_MAP, env)
    if json_states:
        state_map.update(json_states)

    folder_name = _env_str(ENV_PROJECT_DOCS_FOLDER, env) or docs.folder_name

    return config.model_copy(
        update={
            "provider": provider,
            "providers": ProvidersConfig(
                bitrix24=bitrix.model_copy(
                    update={
                        "webhook_url": webhook,
                        "group_id": group_id,
                        "responsible_id": responsible_id,
                        "stage_map": stage_map,
                    }
                ),
                plane=plane.model_copy(
                    update={
                        "api_key": api_key,
                        "base_url": base_url,
                        "workspace_slug": workspace_slug,
                        "project_id": project_id,
                        "state_map": state_map,
                    }
                ),
            ),
            "project_docs": docs.model_copy(update={"folder_name": folder_name}),
        }
    )


def apply_secret_env(config: BoardProjectionConfig) -> BoardProjectionConfig:
    """Backward-compatible alias for apply_env_overrides."""
    return apply_env_overrides(config)


def load_projection_config(
    config_path: Path | str | None = None,
    *,
    project_root: Path | str | None = None,
) -> tuple[BoardProjectionConfig | None, str | None]:
    """
    Load BoardProjectionConfig from path + environment.
    Returns (config, disabled_reason).
    If config is missing, returns (None, 'missing_config').
    If provider is 'none', returns (config, 'provider_none').
    If config is invalid YAML or has unknown provider, raises ProjectionConfigError.
    If provider config is incomplete, returns (config, 'incomplete_provider_config').

    Per-project board settings (provider, group/project ids, stage/state maps, secrets)
    are expected from env and override YAML. See .env.example.
    """
    target_path = resolve_config_path(config_path)
    if not target_path.exists() or not target_path.is_file():
        return None, "missing_config"

    resolved_project_root = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else target_path.parent.parent.resolve()
        if target_path.parent.name == ".loop"
        else target_path.parent.resolve()
    )
    board_env = _load_board_env_from_files(resolved_project_root)

    try:
        raw_content = target_path.read_text(encoding="utf-8")
        raw_data = yaml.safe_load(raw_content) or {}
    except Exception as exc:
        raise ProjectionConfigError(f"Failed to parse YAML from {target_path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ProjectionConfigError(f"Invalid YAML structure in {target_path}: expected dictionary")

    # Provider may be filled later from LOOP_BOARD_PROVIDER; validate after env overlay.
    try:
        config = BoardProjectionConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ProjectionConfigError(f"Invalid board projection configuration: {exc}") from exc

    config = apply_env_overrides(config, env=board_env)

    if config.provider not in SUPPORTED_PROVIDERS:
        raise ProjectionConfigError(
            f"Unknown board projection provider: '{config.provider}'. Supported: {SUPPORTED_PROVIDERS}"
        )

    if config.provider == "none":
        return config, "provider_none"

    is_complete, reason = config.check_provider_completeness()
    if not is_complete:
        return config, reason

    return config, None
