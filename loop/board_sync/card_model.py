"""Canonical task-board card identity, metadata, and display builders."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import yaml
from pydantic import ValidationError

from loop.schemas.board import BoardCardMetadata

_METADATA_SCHEMA = "mb-board-card/v1"
_MAX_CARD_ID_LENGTH = 120
_FOOTER_DELIMITER = "\n---\nmb-board-card/v1\n"


class CardKind(str, Enum):
    """Kinds of cards projected from memory-bank work."""

    STEP = "step"
    GATE = "gate"
    EPIC = "epic"


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


@dataclass(frozen=True, slots=True)
class EpicCard:
    """Metadata for an epic summary card on the board."""

    project_root: str
    workspace_id: str
    role: str
    epic_id: str
    next_command: str
    next_step_id: str | None
    progress_summary: str
    roadmap_rank: int
    sync_generation: int
    hub_dev: str | None = None

    @property
    def card_kind(self) -> CardKind:
        return CardKind.EPIC


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
    elif card_kind is CardKind.EPIC:
        if epic is None:
            raise ValueError("epic stable_id requires epic_id")
        suffix = f"{role_value}-{epic}-epic"
        hash_payload = f"epic{role_value}{epic}"
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


def _metadata(card: StepCard | GateCard | EpicCard) -> dict[str, Any]:
    values = asdict(card)
    values["schema"] = _METADATA_SCHEMA
    values["card_kind"] = card.card_kind.value
    return {key: value for key, value in values.items() if value is not None}


def serialize_metadata(card: StepCard | GateCard | EpicCard) -> str:
    """Serialize card metadata as the machine-readable YAML description block."""
    return compose_description(None, card)


def compose_description(body: str | None, card: StepCard | GateCard | EpicCard) -> str:
    """Compose description with body content followed by metadata footer."""
    yaml_dump = yaml.safe_dump(_metadata(card), allow_unicode=True, sort_keys=False)
    if body:
        return f"{body}{_FOOTER_DELIMITER}{yaml_dump}"
    return f"{_FOOTER_DELIMITER.lstrip('\n')}{yaml_dump}"


def parse_metadata(description: str) -> StepCard | GateCard | EpicCard:
    """Parse and validate a serialized ``mb-board-card/v1`` description."""
    if _FOOTER_DELIMITER in description:
        _, yaml_part = description.rsplit(_FOOTER_DELIMITER, 1)
    elif _FOOTER_DELIMITER.lstrip("\n") in description:
        _, yaml_part = description.rsplit(_FOOTER_DELIMITER.lstrip("\n"), 1)
    else:
        yaml_part = description
    try:
        raw = yaml.safe_load(yaml_part)
    except yaml.YAMLError as exc:
        raise ValueError("invalid card metadata YAML") from exc
    if not isinstance(raw, dict):
        raise ValueError("metadata schema must be mb-board-card/v1")

    try:
        validated = BoardCardMetadata.model_validate(raw)
    except ValidationError as exc:
        field_path = ".".join(str(p) for p in exc.errors()[0]["loc"]) if exc.errors() else "unknown"
        raise ValueError(f"invalid card metadata: error at field '{field_path}'") from exc

    kind = validated.card_kind
    raw_dict = validated.model_dump(by_alias=True, exclude_none=True)
    raw_dict.pop("schema", None)
    raw_dict.pop("card_kind", None)

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
        if not required.issubset(raw_dict):
            missing = required - set(raw_dict.keys())
            raise ValueError(f"step metadata is missing required fields: {missing}")
        return StepCard(**raw_dict)
    if kind == CardKind.GATE.value:
        required = {
            "project_root",
            "workspace_id",
            "role",
            "gate_phase",
            "phase",
            "sync_generation",
        }
        if not required.issubset(raw_dict):
            missing = required - set(raw_dict.keys())
            raise ValueError(f"gate metadata is missing required fields: {missing}")
        raw_dict.setdefault("epic_id", None)
        raw_dict.setdefault("decompose_rel", None)
        return GateCard(**raw_dict)
    if kind == CardKind.EPIC.value:
        required = {
            "project_root",
            "workspace_id",
            "role",
            "epic_id",
            "next_command",
            "progress_summary",
            "roadmap_rank",
            "sync_generation",
        }
        if not required.issubset(raw_dict):
            missing = required - set(raw_dict.keys())
            raise ValueError(f"epic metadata is missing required fields: {missing}")
        raw_dict.setdefault("next_step_id", None)
        return EpicCard(**raw_dict)
    raise ValueError("metadata card_kind must be step, gate, or epic")


def epic_card_title(card: EpicCard) -> str:
    """Build the title for an EpicCard: '[{ROLE}] {epic_id} — next: {next_command} [{next_step_id}] ({progress_summary})'."""
    role = card.role.upper()
    step_part = f" {card.next_step_id}" if card.next_step_id else ""
    summary_part = f" ({card.progress_summary})" if card.progress_summary else ""
    return f"[{role}] {card.epic_id} — next: {card.next_command}{step_part}{summary_part}"


def pending_count(index_yaml: dict[str, Any]) -> int:
    """Return count of pending/in_progress steps in a decompose index dict."""
    steps = index_yaml.get("steps", [])
    if not isinstance(steps, list):
        return 0
    return sum(
        1
        for s in steps
        if isinstance(s, dict) and s.get("status") in ("pending", "in_progress")
    )


def build_title(
    card: StepCard | GateCard | EpicCard,
    step_title: str | None = None,
    *,
    project_label: str | None = None,
    next_epic_id: str | None = None,
) -> str:
    """Build the board title prescribed for a step, gate, or roadmap tip."""
    if isinstance(card, EpicCard):
        return epic_card_title(card)
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


def build_prompt(card: StepCard | GateCard | EpicCard) -> str:
    """Build the exact role command used by the loop for this card."""
    if isinstance(card, EpicCard):
        step_part = f" {card.next_step_id}" if card.next_step_id else ""
        return f"{card.next_command}{step_part}"
    role = card.role.upper()
    if isinstance(card, StepCard):
        return f"{role} IMPLEMENT"
    phase = card.gate_phase.upper()
    return f"{role} {phase}" + (f" {card.epic_id}" if card.epic_id else "")
