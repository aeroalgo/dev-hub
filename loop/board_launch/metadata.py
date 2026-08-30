"""Parse task-board metadata used to launch memory-bank cards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loop.board_sync.card_model import CardKind, GateCard, StepCard, parse_metadata

_METADATA_SCHEMA = "mb-board-card/v1"


_STEP_FIELDS = {
    "schema",
    "card_kind",
    "project_root",
    "workspace_id",
    "role",
    "epic_id",
    "step_id",
    "decompose_rel",
    "phase",
    "sync_generation",
}
_GATE_FIELDS = {
    "schema",
    "card_kind",
    "project_root",
    "workspace_id",
    "role",
    "gate_phase",
    "phase",
    "sync_generation",
    "reason_code",
}


class CardMetadataError(ValueError):
    """Raised when a task-board card cannot be launched safely."""


@dataclass(frozen=True, slots=True)
class LaunchCard:
    """Validated launch fields together with the original metadata mapping."""

    project_root: str
    decompose_rel: str
    step_id: str | None
    gate_phase: str | None
    workspace_id: str | None
    card_kind: CardKind
    raw: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None


def parse_launch_metadata(task_dict: dict[str, Any]) -> LaunchCard:
    """Parse and validate ``mb-board-card/v1`` metadata from a board task."""
    if not isinstance(task_dict, dict):
        raise CardMetadataError("task must be a mapping")

    metadata = task_dict.get("metadata")
    if not isinstance(metadata, dict):
        raise CardMetadataError("task metadata must be a mapping")
    raw = dict(metadata)

    kind = raw.get("card_kind")
    if kind is None or (isinstance(kind, str) and not kind.strip()):
        raise CardMetadataError("metadata card_kind is required")
    if not isinstance(kind, str) or kind not in {CardKind.STEP.value, CardKind.GATE.value}:
        raise CardMetadataError("metadata card_kind must be step or gate")

    project_root = raw.get("project_root")
    if not isinstance(project_root, str) or not project_root.strip():
        raise CardMetadataError("metadata project_root is required")

    decompose_rel = raw.get("decompose_rel")
    if not isinstance(decompose_rel, str) or not decompose_rel.strip():
        raise CardMetadataError("metadata decompose_rel is required")
    if kind == CardKind.GATE.value and not isinstance(decompose_rel, str):
        raise CardMetadataError("metadata decompose_rel must be a string")

    canonical_metadata = _canonical_metadata(raw, kind)
    try:
        parsed = parse_metadata(_as_yaml(canonical_metadata))
    except (TypeError, ValueError) as exc:
        raise CardMetadataError(str(exc)) from exc

    if kind == CardKind.STEP.value and not isinstance(parsed, StepCard):
        raise CardMetadataError("step metadata did not produce a StepCard")
    if kind == CardKind.GATE.value and not isinstance(parsed, GateCard):
        raise CardMetadataError("gate metadata did not produce a GateCard")

    return LaunchCard(
        project_root=project_root,
        decompose_rel=decompose_rel,
        step_id=parsed.step_id if isinstance(parsed, StepCard) else None,
        gate_phase=parsed.gate_phase if isinstance(parsed, GateCard) else None,
        workspace_id=raw.get("workspace_id")
        if isinstance(raw.get("workspace_id"), str)
        else None,
        card_kind=CardKind(kind),
        raw=raw,
        reason_code=raw.get("reason_code")
        if isinstance(raw.get("reason_code"), str)
        else None,
    )


def _canonical_metadata(metadata: dict[str, Any], kind: str) -> dict[str, Any]:
    """Fill launch-only metadata defaults before using the canonical parser."""
    fields = _STEP_FIELDS if kind == CardKind.STEP.value else _GATE_FIELDS
    canonical = {key: value for key, value in metadata.items() if key in fields}
    canonical.setdefault("schema", _METADATA_SCHEMA)
    canonical.setdefault("workspace_id", "launch")
    canonical.setdefault("role", "back")
    canonical.setdefault("phase", "IMPLEMENT" if kind == CardKind.STEP.value else "QA")
    canonical.setdefault("sync_generation", 0)
    if kind == CardKind.STEP.value:
        canonical.setdefault("epic_id", "launch")
        canonical.setdefault("step_id", "launch")
    else:
        canonical.setdefault("epic_id", None)
        canonical.setdefault("decompose_rel", None)
    return canonical


def _as_yaml(metadata: dict[str, Any]) -> str:
    """Serialize task metadata for the canonical board-sync parser."""
    import yaml

    return yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
