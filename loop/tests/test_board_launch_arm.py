from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_launch.arm import (
    ArmResult,
    RoadmapAdvanceDeniedError,
    StepMismatchError,
    arm_from_card,
)
from loop.board_launch.metadata import LaunchCard
from loop.board_sync.card_model import CardKind


def _card(
    tmp_path: Path,
    *,
    kind: CardKind,
    step_id: str | None = None,
    gate_phase: str | None = None,
    **raw: object,
) -> LaunchCard:
    return LaunchCard(
        project_root=str(tmp_path),
        decompose_rel="memory-bank/back/plan/decompose-demo/index.yaml",
        step_id=step_id,
        gate_phase=gate_phase,
        workspace_id="ws-1",
        card_kind=kind,
        raw={"card_kind": kind.value, **raw},
    )


def _seed_project(tmp_path: Path) -> None:
    index = tmp_path / "memory-bank/back/plan/decompose-demo/index.yaml"
    index.parent.mkdir(parents=True)
    index.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "source_md: index.md\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s02\n"
        "  file: s02-demo.yaml\n"
        "  title: Demo step\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    (index.parent / "index.md").write_text(
        "# Demo\n\n| s02 | s02-demo.yaml | Demo step | BACK IMPLEMENT | pending |\n",
        encoding="utf-8",
    )
    (index.parent / "s02-demo.yaml").write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s02\n"
        "plan_id: demo\n"
        "title: Demo step\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: demo\n"
        "context: {}\n"
        "delta: []\n"
        "deletes: []\n"
        "out_of_scope: []\n"
        "skills: {}\n"
        "checkpoints: []\n"
        "tdd: []\n",
        encoding="utf-8",
    )
    (tmp_path / "memory-bank/activeContext.md").write_text(
        "## load_now\n- old\n\n## Handoff\n- old\n", encoding="utf-8"
    )


def test_arm_step_happy(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    card = _card(tmp_path, kind=CardKind.STEP, step_id="s02")

    result = arm_from_card(card)

    assert result == ArmResult(step_id="s02", armed_epic="demo", ok=True)
    assert "s02-demo.yaml" in (tmp_path / "memory-bank/activeContext.md").read_text()


def test_step_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = _card(tmp_path, kind=CardKind.STEP, step_id="s02")
    monkeypatch.setattr(
        "loop.board_launch.arm.arm_session",
        lambda *_args: {"ok": True, "step_id": "s03", "epic_id": "demo"},
    )

    with pytest.raises(StepMismatchError) as exc_info:
        arm_from_card(card)

    assert exc_info.value.diagnostic_code == "step_mismatch"


def test_gate_roadmap_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = _card(tmp_path, kind=CardKind.GATE, gate_phase="ROADMAP")
    called = False

    def arm(*_args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True, "step_id": "s01", "epic_id": "demo"}

    monkeypatch.setattr("loop.board_launch.arm.arm_session", arm)

    with pytest.raises(RoadmapAdvanceDeniedError) as exc_info:
        arm_from_card(card)

    assert exc_info.value.diagnostic_code == "roadmap_advance_denied"
    assert called is False


def test_gate_arm_happy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = _card(tmp_path, kind=CardKind.GATE, gate_phase="QA")
    monkeypatch.setattr(
        "loop.board_launch.arm.arm_session",
        lambda *_args: {"ok": True, "step_id": "QA", "epic_id": "demo"},
    )

    result = arm_from_card(card)

    assert result == ArmResult(step_id="QA", armed_epic="demo", ok=True)


def test_arm_uses_project_root_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = _card(tmp_path / "card-root", kind=CardKind.STEP, step_id="s01")
    calls: list[tuple[Path, str]] = []

    def arm(root: str | Path, decompose: str) -> dict[str, object]:
        calls.append((Path(root), decompose))
        return {"ok": True, "step_id": "s01", "epic_id": "demo"}

    monkeypatch.setattr("loop.board_launch.arm.arm_session", arm)
    arm_from_card(card, cwd_override=tmp_path)

    assert calls == [(tmp_path, card.decompose_rel)]


def test_arm_failure_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    card = _card(tmp_path, kind=CardKind.STEP, step_id="s01")

    def arm(*_args: object) -> dict[str, object]:
        raise RuntimeError("arm failed")

    monkeypatch.setattr("loop.board_launch.arm.arm_session", arm)

    with pytest.raises(RuntimeError, match="arm failed"):
        arm_from_card(card)
