from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PHASES = (
    "DECOMPOSE",
    "PLAN",
    "CLARIFY",
    "ANALYZE",
    "CREATIVE",
    "IMPLEMENT",
    "AUDIT",
    "QA",
    "BUGFIX",
)

PHASE_ENV_NAMES = {
    phase: f"PROJECT_LOOP_{phase}_MODEL" for phase in PHASES
}


def _clean_optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _phase_key(phase: str | None, step_id: str | None) -> str | None:
    step = str(step_id or "").strip().upper()
    if step in PHASES:
        return step
    value = str(phase or "").strip().upper()
    if value == "DONE" or re.search(r"\bDONE\b", value):
        return None
    for candidate in PHASES:
        if re.search(rf"\b{re.escape(candidate)}\b", value):
            return candidate
    return None


def loop_phase_key(phase: str | None, step_id: str | None = None) -> str | None:
    return _phase_key(phase, step_id)


@dataclass(frozen=True)
class ModelSelection:
    model: str | None
    source: Literal["cli", "step_env", "phase_env", "default_env", "missing"]
    phase: str | None
    step_id: str | None
    env_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "model_source": self.source,
            "loop_phase": self.phase,
            "step_id": self.step_id,
            "model_env": self.env_name,
        }


class LoopSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    runtime: Literal["claude", "codex"] = Field(
        default="claude",
        validation_alias=AliasChoices("LOOP_RUNTIME", "EPIC_RUNTIME"),
    )
    model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOOP_MODEL", "PROJECT_LOOP_MODEL"),
    )
    step_models: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "LOOP_STEP_MODELS", "PROJECT_LOOP_STEP_MODELS"
        ),
    )

    decompose_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_DECOMPOSE", "PROJECT_LOOP_DECOMPOSE_MODEL"
        ),
    )
    plan_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOOP_MODEL_PLAN", "PROJECT_LOOP_PLAN_MODEL"),
    )
    clarify_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_CLARIFY", "PROJECT_LOOP_CLARIFY_MODEL"
        ),
    )
    analyze_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_ANALYZE", "PROJECT_LOOP_ANALYZE_MODEL"
        ),
    )
    creative_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_CREATIVE", "PROJECT_LOOP_CREATIVE_MODEL"
        ),
    )
    implement_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_IMPLEMENT", "PROJECT_LOOP_IMPLEMENT_MODEL"
        ),
    )
    audit_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOOP_MODEL_AUDIT", "PROJECT_LOOP_AUDIT_MODEL"),
    )
    qa_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LOOP_MODEL_QA", "PROJECT_LOOP_QA_MODEL"),
    )
    bugfix_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LOOP_MODEL_BUGFIX", "PROJECT_LOOP_BUGFIX_MODEL"
        ),
    )

    session_timeout: int = Field(
        default=3600,
        ge=1,
        validation_alias=AliasChoices("LOOP_SESSION_TIMEOUT"),
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices("LOOP_MAX_ATTEMPTS"),
    )
    max_steps: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices("LOOP_MAX_STEPS"),
    )
    retry_backoff: float = Field(
        default=2.0,
        ge=0,
        validation_alias=AliasChoices("LOOP_RETRY_BACKOFF"),
    )

    workflow_hooks: Literal["loop", "off"] = Field(
        default="loop",
        validation_alias=AliasChoices(
            "LOOP_WORKFLOW_HOOKS", "PROJECT_WORKFLOW_HOOKS"
        ),
    )
    codex_use_omniroute: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "LOOP_CODEX_USE_OMNIROUTE", "CODEX_USE_OMNIROUTE"
        ),
    )
    codex_bin: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CODEX_BIN"),
    )
    claude_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CLAUDE_PATH"),
    )
    codex_omniroute_wrapper: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CODEX_OMNIROUTE_WRAPPER"),
    )
    omniroute_api_url: str = Field(
        default="http://localhost:20128/v1",
        validation_alias=AliasChoices("LOOP_OMNIROUTE_API_URL", "OMNIROUTE_API_URL"),
    )
    omniroute_api_key_file: str = Field(
        default="~/.codex/.omniroute_key",
        validation_alias=AliasChoices(
            "LOOP_OMNIROUTE_API_KEY_FILE", "OMNIROUTE_API_KEY_FILE"
        ),
    )
    codex_allow_unpatched: bool = Field(
        default=False,
        validation_alias=AliasChoices("CODEX_ALLOW_UNPATCHED"),
    )

    @field_validator(
        "model",
        "decompose_model",
        "plan_model",
        "clarify_model",
        "analyze_model",
        "creative_model",
        "implement_model",
        "audit_model",
        "qa_model",
        "bugfix_model",
        "codex_bin",
        "claude_path",
        "codex_omniroute_wrapper",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        return _clean_optional(value) if isinstance(value, str) else value

    @field_validator("step_models", mode="before")
    @classmethod
    def normalize_step_models(cls, value: object) -> object:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return value
        return {
            str(key).strip().upper(): str(model).strip()
            for key, model in value.items()
            if str(model).strip()
        }

    @classmethod
    def load(
        cls,
        *,
        hub_root: str | Path,
        project_root: str | Path | None = None,
    ) -> "LoopSettings":
        hub = Path(hub_root).expanduser().resolve()
        project = Path(project_root).expanduser().resolve() if project_root else hub
        files: list[str] = []
        for candidate in (
            hub / ".env",
            project / ".env",
            hub / "projects" / project.name / ".env.override",
        ):
            if candidate.is_file() and str(candidate) not in files:
                files.append(str(candidate))
        return cls(_env_file=tuple(files) or None)

    def model_for(
        self,
        *,
        phase: str | None,
        step_id: str | None,
        role: str | None = None,
        cli_model: str | None = None,
    ) -> ModelSelection:
        normalized_step = str(step_id or "").strip() or None
        key = _phase_key(phase, step_id)
        cli = _clean_optional(cli_model)
        if cli:
            return ModelSelection(cli, "cli", key, normalized_step)

        step_keys = [
            f"{str(role or '').strip().upper()}:{str(step_id or '').strip().upper()}"
            if role and step_id
            else "",
            f"{str(key or '').strip().upper()}:{str(step_id or '').strip().upper()}"
            if key and step_id
            else "",
            str(step_id or "").strip().upper(),
        ]
        for step_key in step_keys:
            if step_key and self.step_models.get(step_key):
                return ModelSelection(
                    self.step_models[step_key],
                    "step_env",
                    key,
                    normalized_step,
                    "LOOP_STEP_MODELS",
                )

        phase_field = f"{key.lower()}_model" if key else ""
        phase_model = getattr(self, phase_field, None) if phase_field else None
        if phase_model:
            return ModelSelection(
                phase_model,
                "phase_env",
                key,
                normalized_step,
                PHASE_ENV_NAMES.get(key or ""),
            )
        if self.model:
            return ModelSelection(self.model, "default_env", key, normalized_step, "LOOP_MODEL")
        return ModelSelection(
            None,
            "missing",
            key,
            normalized_step,
            PHASE_ENV_NAMES.get(key or "") or "LOOP_MODEL",
        )

    def apply_environment(self) -> None:
        values = {
            "EPIC_RUNTIME": self.runtime,
            "LOOP_WORKFLOW_HOOKS": self.workflow_hooks,
            "CODEX_USE_OMNIROUTE": str(int(self.codex_use_omniroute)),
            "OMNIROUTE_API_URL": self.omniroute_api_url,
            "OMNIROUTE_API_KEY_FILE": self.omniroute_api_key_file,
        }
        if self.codex_bin:
            values["CODEX_BIN"] = self.codex_bin
        if self.claude_path:
            values["CLAUDE_PATH"] = self.claude_path
        if self.codex_omniroute_wrapper:
            values["CODEX_OMNIROUTE_WRAPPER"] = self.codex_omniroute_wrapper
        for key, value in values.items():
            os.environ.setdefault(key, str(value))


def activate_loop_process(*, project_root: str | Path | None = None, session_id: str | None = None) -> None:
    os.environ["LOOP_ACTIVE"] = "1"
    os.environ["EPIC_LOOP"] = "1"
    if project_root:
        os.environ["PROJECT_ROOT"] = str(Path(project_root).resolve())
    if session_id:
        os.environ["LOOP_SESSION_ID"] = str(session_id)


def resolve_loop_phase_model(
    *,
    phase: str | None,
    armed_step: str | None = None,
    cli_model: str | None = None,
    project_dir: str | Path | None = None,
    settings: LoopSettings | None = None,
) -> dict[str, Any]:
    root = Path(project_dir or os.environ.get("PROJECT_ROOT") or Path.cwd()).resolve()
    resolved_settings = settings or LoopSettings.load(hub_root=root, project_root=root)
    return resolved_settings.model_for(
        phase=phase,
        step_id=armed_step,
        cli_model=cli_model,
    ).as_dict()


__all__ = [
    "LoopSettings",
    "ModelSelection",
    "PHASES",
    "PHASE_ENV_NAMES",
    "activate_loop_process",
    "loop_phase_key",
    "resolve_loop_phase_model",
]
