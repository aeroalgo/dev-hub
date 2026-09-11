"""Typed contracts, protocols, and boundaries for the Python loop supervisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable

from harness.hooks._lib import RuntimeConfig


class RunAction(StrEnum):
    """Outer orchestrator action decision."""

    CONTINUE = "continue"
    COMPLETE = "complete"
    HALT = "halt"


@dataclass(frozen=True)
class RunOutcome:
    """Final or intermediate outcome of a loop run."""

    action: RunAction
    exit_code: int
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": str(self.action.value),
            "exit_code": self.exit_code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PreflightCheckResult:
    """Result of preflight, compilation, doctor, and environment checks."""

    ok: bool
    reason: str | None = None
    exit_code: int = 0
    diagnostic_code: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "diagnostic_code": self.diagnostic_code,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class RunnerConfig:
    """Immutable configuration for loop runner instance."""

    hub_root: Path
    project_root: Path
    state_dir: Path
    runtime: RuntimeConfig
    permission_mode: str
    headless: bool
    interactive: bool
    verbose: bool
    cli_model: str | None = None
    epic_spec: str | None = None
    epic_id: str | None = None
    mode: str | None = None
    extra_args: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.hub_root, Path):
            object.__setattr__(self, "hub_root", Path(self.hub_root))
        if not isinstance(self.project_root, Path):
            object.__setattr__(self, "project_root", Path(self.project_root))
        if not isinstance(self.state_dir, Path):
            object.__setattr__(self, "state_dir", Path(self.state_dir))
        if not isinstance(self.extra_args, tuple):
            object.__setattr__(self, "extra_args", tuple(self.extra_args))

    def to_dict(self) -> dict[str, Any]:
        return {
            "hub_root": str(self.hub_root),
            "project_root": str(self.project_root),
            "state_dir": str(self.state_dir),
            "runtime": asdict(self.runtime),
            "permission_mode": self.permission_mode,
            "headless": self.headless,
            "interactive": self.interactive,
            "verbose": self.verbose,
            "cli_model": self.cli_model,
            "epic_spec": self.epic_spec,
            "epic_id": self.epic_id,
            "mode": self.mode,
            "extra_args": list(self.extra_args),
        }


@dataclass(frozen=True)
class SessionRequest:
    """Execution request specification for a single bounded session."""

    session_id: str
    prompt_file: Path
    runtime_id: str
    phase: str
    model: str | None
    mode: Literal["headless", "interactive"] | str
    log_file: Path
    timeout_sec: int
    kill_grace_sec: int
    heartbeat_sec: int | None
    idle_timeout_sec: int | None
    permission_mode: str
    extra_args: tuple[str, ...]
    project_root: Path
    hub_root: Path
    runtime_extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.prompt_file, Path):
            object.__setattr__(self, "prompt_file", Path(self.prompt_file))
        if not isinstance(self.log_file, Path):
            object.__setattr__(self, "log_file", Path(self.log_file))
        if not isinstance(self.project_root, Path):
            object.__setattr__(self, "project_root", Path(self.project_root))
        if not isinstance(self.hub_root, Path):
            object.__setattr__(self, "hub_root", Path(self.hub_root))
        if not isinstance(self.extra_args, tuple):
            object.__setattr__(self, "extra_args", tuple(self.extra_args))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "prompt_file": str(self.prompt_file),
            "runtime_id": self.runtime_id,
            "phase": self.phase,
            "model": self.model,
            "mode": self.mode,
            "log_file": str(self.log_file),
            "timeout_sec": self.timeout_sec,
            "kill_grace_sec": self.kill_grace_sec,
            "heartbeat_sec": self.heartbeat_sec,
            "idle_timeout_sec": self.idle_timeout_sec,
            "permission_mode": self.permission_mode,
            "extra_args": list(self.extra_args),
            "project_root": str(self.project_root),
            "hub_root": str(self.hub_root),
            "runtime_extras": dict(self.runtime_extras),
        }


@dataclass(frozen=True)
class SessionResult:
    """Execution result returned after a bounded session invocation."""

    exit_code: int
    runtime_id: str
    log_file: Path
    interrupted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.log_file, Path):
            object.__setattr__(self, "log_file", Path(self.log_file))

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "runtime_id": self.runtime_id,
            "log_file": str(self.log_file),
            "interrupted": self.interrupted,
        }


@runtime_checkable
class ContextPort(Protocol):
    """Protocol port for domain context operations (prepare, check-after, record-abort)."""

    def prepare_session(
        self,
        cwd: str | Path,
        *,
        model: str | None = None,
        runtime: str | None = None,
        _chain_depth: int = 0,
    ) -> Mapping[str, Any]: ...

    def check_after(
        self,
        cwd: str | Path,
        *,
        fingerprint_before: str | None = None,
    ) -> Mapping[str, Any]: ...

    def record_abort(
        self,
        cwd: str | Path,
        *,
        log_path: str | Path,
        exit_code: int,
        attempt: int = 1,
        runtime: str = "claude",
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class SessionPort(Protocol):
    """Protocol port for bounded session invocation."""

    def invoke(self, request: SessionRequest) -> SessionResult: ...


__all__ = [
    "ContextPort",
    "PreflightCheckResult",
    "RunAction",
    "RunOutcome",
    "RunnerConfig",
    "RuntimeConfig",
    "SessionPort",
    "SessionRequest",
    "SessionResult",
]
