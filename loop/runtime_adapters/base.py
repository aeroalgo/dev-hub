from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Protocol, runtime_checkable

AUTH_BANNED_PATTERNS = (
    re.compile(r"(?i)API Error:\s*401\b"),
    re.compile(r"(?i)\b401\b[^\n]*banned"),
    re.compile(r"(?i)All connections banned"),
    re.compile(r"(?i)connections?\s+banned"),
    re.compile(r"(?i)\bbanned\b"),
)


@dataclass(frozen=True)
class SessionContext:
    prompt: str
    phase: str
    model: str | None = None
    runtime_id: str = "claude"
    session_id: str | None = None
    step: str | None = None
    role: str | None = None
    epoch: int = 0
    invocation_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateLaunchRequest:
    """Immutable request specification for launching a gate verifier subagent."""

    session_id: str
    phase: str
    step: str
    role: str
    epoch: int = 0
    prompt: str = ""
    model: str | None = None
    runtime_id: str = "claude"
    owner: str = "orchestrator"
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def key_tuple(self) -> tuple[str, str, str, str, int]:
        return (self.session_id, self.phase, self.step, self.role, self.epoch)

    @property
    def invocation_key(self) -> Any:
        from loop.lifecycle import InvocationKey
        return InvocationKey(
            session=self.session_id,
            phase=self.phase,
            step=self.step,
            role=self.role,
            epoch=self.epoch,
        )


@dataclass(frozen=True)
class GateLaunchResult:
    """Result of dispatching a gate verifier subagent."""

    invocation_id: str
    key: str
    state: str
    is_new_launch: bool
    receipt: Any | None = None
    status_view: Any | None = None
    first_action_taken: bool = False


@runtime_checkable
class GateDispatcher(Protocol):
    """Protocol for idempotent gate / verifier dispatchers."""

    def dispatch(
        self,
        request: GateLaunchRequest,
        worker_fn: Any | None = None,
    ) -> GateLaunchResult:
        ...


@dataclass(frozen=True)
class SessionAnalysis:
    reason: str | None = None
    retry: bool = False
    dsh_abort_kind: str | None = None
    structured_output: dict[str, Any] | None = None


from pathlib import Path


@dataclass(frozen=True)
class RuntimePreparationResult:
    """Result of runtime binary and profile readiness verification."""

    ok: bool
    exit_code: int = 0
    error: str | None = None
    command: list[str] | None = None


@dataclass(frozen=True)
class RuntimeCapabilities:
    stream_json: bool = False
    model_check: bool = False


@runtime_checkable
class RuntimeAdapter(Protocol):
    def build_command(self, ctx: SessionContext) -> list[str]:
        ...

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        ...

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        ...

    def collaboration_block(self, ctx: SessionContext) -> str:
        ...
