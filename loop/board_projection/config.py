from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field, ValidationError

from loop.board_projection.errors import ProjectionConfigError

DEFAULT_CONFIG_PATH = Path(".loop/board-projection.yaml")
ENV_CONFIG_PATH_VAR = "LOOP_BOARD_PROJECTION_CONFIG"

SUPPORTED_PROVIDERS = {"none", "bitrix24", "plane"}

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
    "CONTEXT_SYNC": "verify",
    "DONE": "done",
    "HALT": "blocked",
}


class Bitrix24Config(BaseModel):
    webhook_url: str = Field(default="", description="Inbound webhook REST endpoint")
    group_id: int | None = Field(default=None, description="Project / Sonet group ID")
    stage_map: dict[str, str] = Field(default_factory=dict, description="Mapping alias -> stageId")

    def is_complete(self) -> bool:
        return bool(self.webhook_url and self.group_id is not None)


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


class BoardProjectionConfig(BaseModel):
    schema_version: str = Field(default="loop-board-projection/v1", alias="schema")
    provider: str = Field(default="none")
    role_allowlist: list[str] = Field(default_factory=lambda: ["back"])
    phase_alias: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_PHASE_ALIASES))
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

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


def load_projection_config(
    config_path: Path | str | None = None,
) -> tuple[BoardProjectionConfig | None, str | None]:
    """
    Load BoardProjectionConfig from path or environment.
    Returns (config, disabled_reason).
    If config is missing, returns (None, 'missing_config').
    If provider is 'none', returns (config, 'provider_none').
    If config is invalid YAML or has unknown provider, raises ProjectionConfigError.
    If provider config is incomplete, returns (config, 'incomplete_provider_config').
    """
    target_path = resolve_config_path(config_path)
    if not target_path.exists() or not target_path.is_file():
        return None, "missing_config"

    try:
        raw_content = target_path.read_text(encoding="utf-8")
        raw_data = yaml.safe_load(raw_content) or {}
    except Exception as exc:
        raise ProjectionConfigError(f"Failed to parse YAML from {target_path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ProjectionConfigError(f"Invalid YAML structure in {target_path}: expected dictionary")

    provider = str(raw_data.get("provider", "none")).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ProjectionConfigError(f"Unknown board projection provider: '{provider}'. Supported: {SUPPORTED_PROVIDERS}")

    try:
        config = BoardProjectionConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ProjectionConfigError(f"Invalid board projection configuration: {exc}") from exc

    if config.provider == "none":
        return config, "provider_none"

    is_complete, reason = config.check_provider_completeness()
    if not is_complete:
        return config, reason

    return config, None
