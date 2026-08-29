from __future__ import annotations

import pytest

from loop.board_launch.metadata import (
    CardMetadataError,
    LaunchCard,
    parse_launch_metadata,
)
from loop.board_sync.card_model import CardKind, GateCard, StepCard


def test_parse_valid_step() -> None:
    metadata = {
        "schema": "mb-board-card/v1",
        "card_kind": "step",
        "project_root": "/p",
        "workspace_id": "ws-1",
        "decompose_rel": "memory-bank/back/plan/decompose-T-HUB-015/index.yaml",
        "step_id": "s02",
        "role": "back",
        "epic_id": "T-HUB-015",
    }

    card = parse_launch_metadata({"metadata": metadata})

    assert isinstance(card, LaunchCard)
    assert card.project_root == "/p"
    assert card.decompose_rel == metadata["decompose_rel"]
    assert card.step_id == "s02"
    assert card.gate_phase is None
    assert card.workspace_id == "ws-1"
    assert card.card_kind is CardKind.STEP
    assert card.raw == metadata


def test_parse_valid_gate() -> None:
    card = parse_launch_metadata(
        {
            "metadata": {
                "card_kind": "gate",
                "project_root": "/p",
                "decompose_rel": "memory-bank/back/plan/decompose-T-HUB-015/index.yaml",
                "gate_phase": "QA",
            }
        }
    )

    assert card.card_kind is CardKind.GATE
    assert card.gate_phase == "QA"
    assert card.step_id is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"project_root": "/p", "decompose_rel": "x"},
        {"card_kind": "step", "decompose_rel": "x"},
        {"card_kind": "unknown", "project_root": "/p", "decompose_rel": "x"},
    ],
)
def test_parse_invalid(metadata: dict[str, object]) -> None:
    with pytest.raises(CardMetadataError):
        parse_launch_metadata({"metadata": metadata})


def test_parse_missing_project_root() -> None:
    with pytest.raises(CardMetadataError, match="project_root"):
        parse_launch_metadata(
            {"metadata": {"card_kind": "step", "decompose_rel": "x"}}
        )


def test_parse_missing_decompose_rel() -> None:
    with pytest.raises(CardMetadataError, match="decompose_rel"):
        parse_launch_metadata(
            {"metadata": {"card_kind": "gate", "project_root": "/p"}}
        )


def test_parse_workspace_id_optional() -> None:
    card = parse_launch_metadata(
        {"metadata": {"card_kind": "step", "project_root": "/p", "decompose_rel": "x", "step_id": "s01"}}
    )

    assert card.workspace_id is None


def test_card_kind_routing() -> None:
    step = parse_launch_metadata(
        {"metadata": {"card_kind": "step", "project_root": "/p", "decompose_rel": "x", "step_id": "s01"}}
    )
    gate = parse_launch_metadata(
        {"metadata": {"card_kind": "gate", "project_root": "/p", "decompose_rel": "x", "gate_phase": "QA"}}
    )

    assert step.card_kind is CardKind.STEP
    assert gate.card_kind is CardKind.GATE
    assert StepCard is not GateCard


def test_import_card_kind_from_board_sync() -> None:
    from loop.board_launch import metadata
    from loop.board_sync import card_model

    assert metadata.CardKind is card_model.CardKind
