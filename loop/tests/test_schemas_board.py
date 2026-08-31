"""Tests for loop.schemas.board (BoardCardMetadata) integration with card_model."""

import pytest
from pydantic import ValidationError

from loop.board_sync.card_model import (
    CardKind,
    GateCard,
    StepCard,
    compose_description,
    parse_metadata,
)
from loop.schemas.board import BoardCardMetadata


def test_board_card_metadata_valid_step():
    meta = BoardCardMetadata(
        card_kind="step",
        project_root="/path/to/root",
        workspace_id="ws1",
        role="back",
        sync_generation=1,
        epic_id="T-HUB-022",
        step_id="s06",
        decompose_rel="memory-bank/back/plan/decompose-T-HUB-022",
        phase="BACK IMPLEMENT",
    )
    assert meta.card_kind == "step"
    assert meta.schema_version == "mb-board-card/v1"


def test_board_card_metadata_invalid_kind():
    with pytest.raises(ValidationError):
        BoardCardMetadata(
            card_kind="unknown_kind",
            project_root="/path/to/root",
            workspace_id="ws1",
            role="back",
            sync_generation=1,
        )


def test_parse_metadata_invalid_footer_field_error():
    desc = """Some card body
---
mb-board-card/v1
schema: mb-board-card/v1
card_kind: step
project_root: /root
workspace_id: ws1
role: back
sync_generation: "not-an-int"
"""
    with pytest.raises(ValueError, match="invalid card metadata: error at field 'sync_generation'"):
        parse_metadata(desc)


def test_parse_metadata_valid_step_roundtrip():
    step_card = StepCard(
        project_root="/root",
        workspace_id="ws1",
        role="back",
        epic_id="T-HUB-022",
        step_id="s06",
        decompose_rel="rel/path",
        phase="BACK IMPLEMENT",
        sync_generation=10,
    )
    desc = compose_description("Task body", step_card)
    parsed = parse_metadata(desc)
    assert isinstance(parsed, StepCard)
    assert parsed.epic_id == "T-HUB-022"
    assert parsed.step_id == "s06"
    assert parsed.sync_generation == 10


def test_parse_metadata_missing_required_step_fields():
    desc = """
---
mb-board-card/v1
schema: mb-board-card/v1
card_kind: step
project_root: /root
workspace_id: ws1
role: back
sync_generation: 1
"""
    with pytest.raises(ValueError, match="step metadata is missing required fields"):
        parse_metadata(desc)
