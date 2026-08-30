"""Run the product loop and normalize its host-visible execution result."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .loop_argv import BridgeConfig, LoopArgvResult
from .metadata import LaunchCard

_DEFAULT_TIMEOUT = 300.0
_LOCK_CONFLICT_EXIT_CODES = frozenset({1})
_MAX_LOG_BYTES = 100_000


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Normalized result of one loop subprocess execution."""

    status: str
    exit_code: int | None
    log_path: Path | None = None
    diagnostic_code: str | None = None
    model_source: str | None = None
    model_env: str | None = None


class LoopRunError(RuntimeError):
    """Raised when the loop cannot be spawned or completes by timeout."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: str,
        exit_code: int | None = None,
        log_path: Path | None = None,
        model_source: str | None = None,
        model_env: str | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.exit_code = exit_code
        self.log_path = log_path
        self.model_source = model_source
        self.model_env = model_env


def execution_result_from_error(
    error: LoopRunError,
    argv_result: LoopArgvResult | None = None,
) -> ExecutionResult:
    """Convert a spawn/timeout error into the common failed result shape."""
    return ExecutionResult(
        status="failed",
        exit_code=error.exit_code,
        log_path=error.log_path,
        diagnostic_code=error.diagnostic_code,
        model_source=(
            argv_result.model_source if argv_result is not None else error.model_source
        ),
        model_env=argv_result.model_env if argv_result is not None else error.model_env,
    )


class FakeLoopRunner:
    """Callable loop runner for pipeline and host tests."""

    def __init__(self, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.calls: list[tuple[LaunchCard, LoopArgvResult, BridgeConfig]] = []

    def __call__(
        self,
        launch_card: LaunchCard,
        argv_result: LoopArgvResult,
        config: BridgeConfig,
    ) -> ExecutionResult:
        self.calls.append((launch_card, argv_result, config))
        return ExecutionResult(
            status="succeeded" if self.exit_code == 0 else "failed",
            exit_code=self.exit_code,
            model_source=argv_result.model_source,
            model_env=argv_result.model_env,
        )


def loop_run(
    launch_card: LaunchCard,
    argv_result: LoopArgvResult,
    config: BridgeConfig,
    *,
    loop_bin_override: Path | None = None,
) -> ExecutionResult:
    """Spawn the loop without a shell and capture its output in a bounded log."""
    del config
    project_root = Path(launch_card.project_root)
    argv = list(argv_result.argv)
    if loop_bin_override is not None:
        if not argv:
            raise LoopRunError(
                "loop argv is empty",
                diagnostic_code="empty_argv",
                model_source=argv_result.model_source,
                model_env=argv_result.model_env,
            )
        argv[0] = str(loop_bin_override)

    env = os.environ.copy()
    env.update(argv_result.env_extra)
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise LoopRunError(
            f"failed to spawn loop: {exc}",
            diagnostic_code="spawn_error",
            model_source=argv_result.model_source,
            model_env=argv_result.model_env,
        ) from exc

    try:
        stdout, stderr = process.communicate(timeout=_DEFAULT_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        log_path = _write_log(_as_text(stdout) + _as_text(stderr))
        raise LoopRunError(
            f"loop timed out after {_DEFAULT_TIMEOUT:g}s",
            diagnostic_code="timeout",
            log_path=log_path,
            model_source=argv_result.model_source,
            model_env=argv_result.model_env,
        ) from exc
    except OSError as exc:
        raise LoopRunError(
            f"failed to collect loop output: {exc}",
            diagnostic_code="communicate_error",
            model_source=argv_result.model_source,
            model_env=argv_result.model_env,
        ) from exc

    if process.returncode is None:
        raise LoopRunError(
            "loop exited without a return code",
            diagnostic_code="missing_exit_code",
            model_source=argv_result.model_source,
            model_env=argv_result.model_env,
        )

    output = _as_text(stdout) + _as_text(stderr)
    log_path = _write_log(output)
    exit_code = process.returncode
    diagnostic_code = (
        "lock_conflict"
        if _is_lock_conflict(exit_code, output)
        else None
    )
    return ExecutionResult(
        status="succeeded" if exit_code == 0 else "failed",
        exit_code=exit_code,
        log_path=log_path,
        diagnostic_code=diagnostic_code,
        model_source=argv_result.model_source,
        model_env=argv_result.model_env,
    )


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _is_lock_conflict(exit_code: int | None, output: str) -> bool:
    lowered = output.lower()
    return exit_code in _LOCK_CONFLICT_EXIT_CODES and (
        "another loop runner is already active" in lowered
        or "lock conflict" in lowered
        or "lock_conflict" in lowered
        or "resource temporarily unavailable" in lowered
        or "eagain" in lowered
    )


def _write_log(output: str) -> Path:
    dev_hub = Path(os.environ.get("DEV_HUB", "."))
    runtime_dir = dev_hub / "loop" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = runtime_dir / f"exec-{stamp}.log"
    encoded = output.encode("utf-8", errors="replace")
    if len(encoded) > _MAX_LOG_BYTES:
        encoded = encoded[-_MAX_LOG_BYTES:]
    log_path.write_bytes(encoded)
    return log_path
