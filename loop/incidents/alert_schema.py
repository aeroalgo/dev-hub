"""Dataclass and schema definitions for loop-alert/v1 webhooks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class LoopAlertV1Payload:
    schema: str = "loop-alert/v1"
    incident_id: str = ""
    diagnostic_codes: List[str] = field(default_factory=list)
    epic_id: str = ""
    step_id: str = ""
    project_root: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
