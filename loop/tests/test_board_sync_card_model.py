from __future__ import annotations

import hashlib

import pytest

from loop.board_sync.card_model import (
    CardKind,
    GateCard,
    StepCard,
    build_prompt,
    build_title,
    parse_metadata,
    serialize_metadata,
    stable_id,
)

STEP = StepCard(
    project_root="/workspaces/demo",
    workspace_id="ABC/123",
    role="back",
    epic_id="T-HUB-007/dsh-profiles",
    step_id="s02",
    decompose_rel="memory-bank/back/plan/decompose-T-HUB-007/index.yaml",
    phase="IMPLEMENT",
    sync_generation=42,
)
GATE = GateCard(
    project_root="/workspaces/demo",
    workspace_id="ABC/123",
    role="back",
    epic_id="T-HUB-007/dsh-profiles",
    gate_phase="QA",
    decompose_rel="memory-bank/back/plan/decompose-T-HUB-007/index.yaml",
    phase="QA",
    sync_generation=42,
    reason_code="qa_required",
)


def test_stable_id() -> None:
    assert stable_id(
        kind="step",
        ws_id="abc",
        role="back",
        epic_id="T-HUB-007",
        step_id="s02",
    ) == "mb-abc-back-t-hub-007-s02"
    assert stable_id(
        kind=CardKind.GATE,
        ws_id="abc",
        role="back",
        epic_id="T-HUB-007",
        gate_phase="QA",
    ) == "mb-abc-back-t-hub-007-gate-qa"
    assert stable_id(
        kind="gate",
        ws_id="abc",
        role="front",
        gate_phase="ROADMAP",
    ) == "mb-abc-gate-roadmap"

    long_epic = "epic/" + ("x" * 140)
    result = stable_id(
        kind="step",
        ws_id="abc",
        role="back",
        epic_id=long_epic,
        step_id="s01",
    )
    payload = "step" + "back" + long_epic.lower().replace("/", "-") + "s01"
    expected = "mb-abc-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
    assert result == expected
    assert len(result) <= 120


def test_metadata_roundtrip() -> None:
    assert parse_metadata(serialize_metadata(STEP)) == STEP
    assert parse_metadata(serialize_metadata(GATE)) == GATE
    assert "schema: mb-board-card/v1" in serialize_metadata(STEP)
    assert "card_kind: gate" in serialize_metadata(GATE)


def test_title_prompt() -> None:
    assert build_title(STEP, "epic-implement-profile") == (
        "[BACK] T-HUB-007/dsh-profiles s02 — epic-implement-profile"
    )
    assert build_prompt(STEP) == "BACK IMPLEMENT"
    assert build_title(GATE) == "[GATE][BACK] T-HUB-007/dsh-profiles — QA"
    assert build_prompt(GATE) == "BACK QA T-HUB-007/dsh-profiles"

    roadmap = GateCard(
        project_root="/workspaces/demo",
        workspace_id="abc",
        role="back",
        epic_id=None,
        gate_phase="ROADMAP",
        decompose_rel=None,
        phase="ROADMAP",
        sync_generation=1,
    )
    assert build_title(roadmap, project_label="dev-hub", next_epic_id="T-HUB-014") == (
        "[GATE][ROADMAP] dev-hub — next T-HUB-014"
    )
    assert build_prompt(roadmap) == "BACK ROADMAP"


def test_card_kind_enum() -> None:
    assert CardKind.STEP.value == "step"
    assert CardKind.GATE.value == "gate"


def test_metadata_rejects_invalid_schema() -> None:
    with pytest.raises(ValueError, match="schema"):
        parse_metadata("schema: other/v1\ncard_kind: step\n")
