"""Orchestrate board-card arm, loop execution, and optional synchronization."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from .arm import ArmResult, arm_from_card
from .loop_argv import BridgeConfig, LoopArgvResult, build_loop_argv
from .loop_run import ExecutionResult, loop_run
from .metadata import LaunchCard


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Normalized result of the arm/loop pipeline."""

    status: str
    arm: ArmResult | None
    loop: ExecutionResult | None
    loop_invoked: bool
    model_source: str | None = None
    model_env: str | None = None
    sync_warning: str | None = None


def arm_loop_from_card(
    launch_card: LaunchCard,
    config: BridgeConfig,
    *,
    preset_id: str | None = None,
    runtime: str | None = None,
    loop_runner: Callable[
        [LaunchCard, LoopArgvResult, BridgeConfig], ExecutionResult
    ] | None = None,
    arm_fn: Callable[[LaunchCard], ArmResult] | None = None,
) -> PipelineResult:
    """Arm a card, run its loop, and optionally refresh the task board.

    Arming is fail-closed: any arm error prevents argv construction and loop
    execution. Board synchronization is deliberately best-effort and never
    changes the loop status.
    """
    arm_callable = arm_fn or arm_from_card
    try:
        arm_result = (
            arm_callable(launch_card, config=config)
            if arm_fn is None
            else arm_callable(launch_card)
        )
    except Exception:
        return PipelineResult(
            status="arm_failed",
            arm=None,
            loop=None,
            loop_invoked=False,
        )

    phase = _card_phase(launch_card)
    argv_result = build_loop_argv(
        launch_card.project_root,
        phase,
        config,
        preset_id=preset_id,
        runtime=runtime if runtime is not None else config.default_runtime,
    )
    runner = loop_runner or loop_run
    loop_result = runner(launch_card, argv_result, config)
    sync_warning = (
        _sync_after_loop(launch_card.workspace_id, config)
        if config.sync_after_loop
        else None
    )
    return PipelineResult(
        status=loop_result.status,
        arm=arm_result,
        loop=loop_result,
        loop_invoked=True,
        model_source=loop_result.model_source or argv_result.model_source,
        model_env=loop_result.model_env or argv_result.model_env,
        sync_warning=sync_warning,
    )


def _card_phase(launch_card: LaunchCard) -> str:
    """Return the phase used for phase-specific model precedence."""
    raw_phase = launch_card.raw.get("phase")
    if isinstance(raw_phase, str) and raw_phase.strip():
        return raw_phase
    if launch_card.gate_phase:
        return launch_card.gate_phase
    return "IMPLEMENT"


def _sync_after_loop(workspace_id: str | None, config: BridgeConfig) -> str | None:
    """Run board sync and return a warning instead of raising on failure."""
    del config
    command = ["hub-board", "sync"]
    if workspace_id:
        command.extend(["--workspace-id", workspace_id])
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return f"hub-board sync failed to start: {exc}"

    if result.returncode == 0:
        return None
    detail = (result.stderr or result.stdout or "").strip()
    suffix = f": {detail}" if detail else ""
    return f"hub-board sync failed (exit code {result.returncode}){suffix}"


__all__ = ["PipelineResult", "arm_loop_from_card"]
