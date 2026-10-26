from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class EpicRef:
    epic_id: str
    title: str = ""
    description: str = ""
    phase: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionResult:
    status: str
    external_id: str | None = None
    stage_id: str | None = None
    error: str | None = None
    disabled_reason: str | None = None


@runtime_checkable
class BoardProjectionAdapter(Protocol):
    """Protocol for external task board adapters (Bitrix24, Plane, etc.)."""

    @property
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'bitrix24', 'plane')."""
        ...

    def ensure_card(self, epic: EpicRef) -> str:
        """Ensure card exists on the external board, returning its external_id."""
        ...

    def move_card(self, external_id: str, phase: str) -> None:
        """Move card to the column corresponding to the given phase."""
        ...
