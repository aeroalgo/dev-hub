"""Safe host-facing helpers for the DSH mb-card bridge."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, TypeVar

from .loop_argv import BridgeConfig, PresetEntry

MB_STOCK_RUN_ERROR = "mb_card_requires_loop_run"
_ALLOWED_SUBCOMMANDS = frozenset({"arm", "loop", "arm-loop"})
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._/-]+$")
T = TypeVar("T")


class StockRunDeniedError(RuntimeError):
    """Raised when a memory-bank card would use the stock agent runner."""

    diagnostic_code = MB_STOCK_RUN_ERROR

    def __init__(self) -> None:
        super().__init__(MB_STOCK_RUN_ERROR)


def build_hub_board_argv(subcommand: str, task_id: str) -> list[str]:
    """Build fixed argv for a bridge action without shell interpolation."""
    if subcommand not in _ALLOWED_SUBCOMMANDS:
        raise ValueError(f"unsupported board action: {subcommand}")
    if not _SAFE_TOKEN.fullmatch(task_id):
        raise ValueError("task_id contains an unsafe token")
    return ["hub-board", subcommand, "--task-id", task_id]


def intercept_card_run(
    task: dict[str, object],
    stock_handler: Callable[[dict[str, object]], T],
    bridge_handler: Callable[[dict[str, object]], T] | None = None,
) -> T:
    """Route mb-* cards through the bridge and preserve stock behavior otherwise."""
    task_id = task.get("id")
    if isinstance(task_id, str) and task_id.startswith("mb-"):
        if bridge_handler is None:
            raise StockRunDeniedError
        return bridge_handler(task)
    return stock_handler(task)


def load_bridge_config(raw: dict[str, Any]) -> BridgeConfig:
    """Load and validate the ``mb-bridge`` section from Cordis config."""
    section = raw.get("mb-bridge", raw)
    if not isinstance(section, dict):
        raise ValueError("mb-bridge config must be a mapping")
    enabled = section.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("mb-bridge.enabled must be a boolean")
    if not enabled:
        raise ValueError("mb-bridge is disabled")

    allow_roadmap_advance = section.get("allowRoadmapAdvance", False)
    if not isinstance(allow_roadmap_advance, bool):
        raise ValueError("mb-bridge.allowRoadmapAdvance must be a boolean")

    dev_hub = section.get("devHub")
    loop_bin = section.get("loopBin", "bin/loop")
    if not isinstance(loop_bin, str) or not loop_bin.strip():
        raise ValueError("mb-bridge.loopBin must be a non-empty string")
    resolved_loop_bin = Path(loop_bin).expanduser()
    if dev_hub is not None:
        if not isinstance(dev_hub, str) or not dev_hub.strip():
            raise ValueError("mb-bridge.devHub must be a non-empty string")
        resolved_loop_bin = Path(dev_hub).expanduser() / resolved_loop_bin

    default_args = _tokens(section.get("defaultLoopArgs", []), "defaultLoopArgs")
    presets = []
    raw_presets = section.get("modelPresets", [])
    if not isinstance(raw_presets, list):
        raise ValueError("mb-bridge.modelPresets must be a list")
    for item in raw_presets:
        if not isinstance(item, dict):
            raise ValueError("mb-bridge.modelPresets entries must be mappings")
        preset_id = item.get("id")
        label = item.get("label", preset_id)
        if not isinstance(preset_id, str) or not isinstance(label, str):
            raise ValueError("model preset id and label must be strings")
        presets.append(
            PresetEntry(
                id=preset_id,
                label=label,
                args=_tokens(item.get("args", []), f"preset {preset_id}"),
            )
        )

    runtime = section.get("defaultRuntime", "claude")
    if runtime not in {"claude", "dsh"}:
        raise ValueError("mb-bridge.defaultRuntime must be claude or dsh")
    sync_after_loop = section.get("syncAfterLoop", True)
    if not isinstance(sync_after_loop, bool):
        raise ValueError("mb-bridge.syncAfterLoop must be a boolean")
    return BridgeConfig(
        loop_bin=resolved_loop_bin,
        model_presets=presets,
        default_loop_args=default_args,
        default_runtime=runtime,
        allow_roadmap_advance=allow_roadmap_advance,
        sync_after_loop=sync_after_loop,
        enabled=enabled,
    )


def _tokens(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(token, str) for token in value):
        raise ValueError(f"mb-bridge.{name} must be a list of strings")
    if not all(_SAFE_TOKEN.fullmatch(token) for token in value):
        raise ValueError(f"mb-bridge.{name} contains an unsafe token")
    return list(value)


__all__ = [
    "MB_STOCK_RUN_ERROR",
    "StockRunDeniedError",
    "build_hub_board_argv",
    "intercept_card_run",
    "load_bridge_config",
]
