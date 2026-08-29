"""Build the subprocess argv and environment for a board launch."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")
_MAX_PRESETS = 8


class PresetError(ValueError):
    """Raised when a requested model preset is unknown or unsafe."""


@dataclass(frozen=True, slots=True)
class PresetEntry:
    """One user-selectable model preset."""

    id: str
    label: str
    args: list[str]

    def __post_init__(self) -> None:
        if not self.id:
            raise PresetError("preset id must not be empty")
        if not all(isinstance(token, str) for token in self.args):
            raise PresetError(f"invalid token in preset {self.id!r}")

    def validate_args(self) -> None:
        if not all(_TOKEN_RE.fullmatch(token) for token in self.args):
            raise PresetError(f"invalid token in preset {self.id!r}")


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    """Configuration used by the board launch bridge."""

    loop_bin: str | Path
    model_presets: list[PresetEntry] = field(default_factory=list)
    default_loop_args: list[str] = field(default_factory=list)
    default_runtime: str = "host"
    allow_roadmap_advance: bool = False
    sync_after_loop: bool = True

    def __post_init__(self) -> None:
        if len(self.model_presets) > _MAX_PRESETS:
            raise ValueError("model presets must contain at most 8 entries")


@dataclass(frozen=True, slots=True)
class LoopArgvResult:
    """Launch command plus environment additions and precedence diagnostic."""

    argv: list[str]
    env_extra: dict[str, str]
    model_source: str


def _project_env_model(project_root: Path, phase: str) -> str | None:
    """Read the phase model override from the product checkout env file."""
    env_path = project_root / ".claude" / "project.env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    key = f"PROJECT_LOOP_{phase.upper()}_MODEL"
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            value = value.strip()
            if value and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]
            return value or None
    return None


def _base_argv(project_root: Path, config: BridgeConfig) -> list[str]:
    return [str(config.loop_bin), str(project_root)]


def build_loop_argv(
    project_root: str | Path,
    phase: str,
    config: BridgeConfig,
    preset_id: str | None = None,
    runtime: str | None = None,
) -> LoopArgvResult:
    """Build a fail-closed launch command following model precedence rules."""
    root = Path(project_root)
    argv = _base_argv(root, config)
    env_extra = {"EPIC_RUNTIME": "dsh"} if runtime == "dsh" else {}

    if _project_env_model(root, phase) is not None:
        return LoopArgvResult(argv=argv, env_extra=env_extra, model_source="env")

    if preset_id is not None:
        preset = next((entry for entry in config.model_presets if entry.id == preset_id), None)
        if preset is None:
            raise PresetError(f"unknown preset: {preset_id}")
        preset.validate_args()
        argv.extend(preset.args)
        return LoopArgvResult(argv=argv, env_extra=env_extra, model_source="preset")

    if config.default_loop_args:
        argv.extend(config.default_loop_args)
        return LoopArgvResult(argv=argv, env_extra=env_extra, model_source="default")

    return LoopArgvResult(argv=argv, env_extra=env_extra, model_source="bare")
