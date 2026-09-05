"""Protocol and dataclasses for tool gate adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol, runtime_checkable


@dataclass
class ToolGateContext:
    """Context passed to a tool gate adapter check."""
    cwd: Path
    phase: str
    pack_id: str
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolGateResult:
    """Result returned by a tool gate adapter check."""
    ok: bool
    diagnostic_codes: List[str] = field(default_factory=list)


@runtime_checkable
class ToolGateAdapter(Protocol):
    """Protocol for external tool gate adapters."""
    id: str

    def check(self, ctx: ToolGateContext) -> ToolGateResult:
        """Execute check and return ToolGateResult."""
        ...
