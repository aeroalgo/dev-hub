from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class SessionContext:
    prompt: str
    phase: str
    model: str | None = None
    runtime_id: str = "claude"
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionAnalysis:
    reason: str | None = None
    retry: bool = False
    dsh_abort_kind: str | None = None
    structured_output: dict[str, Any] | None = None


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
