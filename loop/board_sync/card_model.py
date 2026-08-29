"""Canonical task-board card identity, metadata, and display builders."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import yaml

_METADATA_SCHEMA = "mb-board-card/v1"
_MAX_CARD_ID_LENGTH = 120


class CardKind(str, Enum):
    """Kinds of cards projected from memory-bank work."""

    STEP = "step"
    GATE = "gate"


@dataclass(frozen=True, slots=True)
class StepCard:
    """Metadata for a pending or active implementation step."""

    project_root: str
    workspace_id: str
    role: str
    epic_id: str
    step_id: str
    decompose_rel: str
    phase: str
    sync_generation: int
    hub_dev: str | None = None

    @property
    def card_kind(self) -> CardKind:
        return CardKind.STEP


@dataclass(frozen=True, slots=True)
class GateCard:
    """Metadata for a workflow gate without a step identifier."""

    project_root: str
    workspace_id: str
    role: str
    epic_id: str | None
    gate_phase: str
    decompose_rel: str | None
    phase: str
    sync_generation: int
    reason_code: str | None = None
    hub_dev: str | None = None

    @property
    def card_kind(self) -> CardKind:
        return CardKind.GATE


def _normalise(value: str) -> str:
    return value.replace("/", "-").lower()


def stable_id(
    *,
    kind: CardKind | str,
    ws_id: str,
    role: str,
    epic_id: str | None = None,
    step_id: str | None = None,
    gate_phase: str | None = None,
) -> str:
    """Return the canonical stable board ID for a step or gate card."""
    card_kind = CardKind(kind)
    workspace = _normalise(ws_id)
    role_value = _normalise(role)
    epic = _normalise(epic_id) if epic_id is not None else None

    if card_kind is CardKind.STEP:
        if epic is None or step_id is None:
            raise ValueError("step stable_id requires epic_id and step_id")
        suffix = f"{role_value}-{epic}-{_normalise(step_id)}"
        hash_payload = f"step{role_value}{epic}{_normalise(step_id)}"
    elif epic is None and _normalise(gate_phase or "") == "roadmap":
        suffix = "gate-roadmap"
        hash_payload = "gateroadmap"
    else:
        if epic is None or gate_phase is None:
            raise ValueError("gate stable_id requires epic_id and gate_phase")
        gate = _normalise(gate_phase)
        suffix = f"{role_value}-{epic}-gate-{gate}"
        hash_payload = f"gate{role_value}{epic}{gate}"

    result = f"mb-{workspace}-{suffix}"
    if len(result) <= _MAX_CARD_ID_LENGTH:
        return result
    return f"mb-{workspace}-{hashlib.sha256(hash_payload.encode()).hexdigest()[:16]}"


def _metadata(card: StepCard | GateCard) -> dict[str, Any]:
    values = asdict(card)
    values["schema"] = _METADATA_SCHEMA
    values["card_kind"] = card.card_kind.value
    return {key: value for key, value in values.items() if value is not None}


def serialize_metadata(card: StepCard | GateCard) -> str:
    """Serialize card metadata as the machine-readable YAML description block."""
    return yaml.safe_dump(_metadata(card), allow_unicode=True, sort_keys=False)


def parse_metadata(description: str) -> StepCard | GateCard:
    """Parse and validate a serialized ``mb-board-card/v1`` description."""
    try:
        raw = yaml.safe_load(description)
    except yaml.YAMLError as exc:
        raise ValueError("invalid card metadata YAML") from exc
    if not isinstance(raw, dict) or raw.get("schema") != _METADATA_SCHEMA:
        raise ValueError("metadata schema must be mb-board-card/v1")

    kind = raw.pop("card_kind", None)
    raw.pop("schema", None)
    if kind == CardKind.STEP.value:
        required = {
            "project_root",
            "workspace_id",
            "role",
            "epic_id",
            "step_id",
            "decompose_rel",
            "phase",
            "sync_generation",
        }
        if not required.issubset(raw):
            raise ValueError("step metadata is missing required fields")
        return StepCard(**raw)
    if kind == CardKind.GATE.value:
        required = {
            "project_root",
            "workspace_id",
            "role",
            "gate_phase",
            "phase",
            "sync_generation",
        }
        if not required.issubset(raw):
            raise ValueError("gate metadata is missing required fields")
        return GateCard(**raw)
    raise ValueError("metadata card_kind must be step or gate")


def build_title(
    card: StepCard | GateCard,
    step_title: str | None = None,
    *,
    project_label: str | None = None,
    next_epic_id: str | None = None,
) -> str:
    """Build the board title prescribed for a step, gate, or roadmap tip."""
    role = card.role.upper()
    if isinstance(card, StepCard):
        if step_title is None:
            raise ValueError("step title requires step_title")
        return f"[{role}] {card.epic_id} {card.step_id} — {step_title}"
    if card.gate_phase.upper() == "ROADMAP" and card.epic_id is None:
        if project_label is None or next_epic_id is None:
            raise ValueError("roadmap title requires project_label and next_epic_id")
        return f"[GATE][ROADMAP] {project_label} — next {next_epic_id}"
    if card.epic_id is None:
        raise ValueError("non-roadmap gate title requires epic_id")
    return f"[GATE][{role}] {card.epic_id} — {card.gate_phase.upper()}"


def build_prompt(card: StepCard | GateCard) -> str:
    """Build the exact role command used by the loop for this card."""
    role = card.role.upper()
    if isinstance(card, StepCard):
        return f"{role} IMPLEMENT"
    phase = card.gate_phase.upper()
    return f"{role} {phase}" + (f" {card.epic_id}" if card.epic_id else "")
