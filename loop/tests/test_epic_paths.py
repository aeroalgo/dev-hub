"""Tests for loop.paths.epic_paths module (resolve_epic_path and EpicPathKind)."""

import pytest
from pathlib import Path

from loop.paths.epic_paths import (
    EpicPathKind,
    resolve_epic_path,
)
from loop.workflow.schemas import WorkflowPack


@pytest.fixture
def software_pack() -> WorkflowPack:
    return WorkflowPack(
        id="dev-hub-software",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
    )


@pytest.fixture
def video_pack() -> WorkflowPack:
    return WorkflowPack(
        id="video-production",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank/video",
        rules_root=".cursor/rules",
        artifact_layout="production-epic-v1",
    )


@pytest.fixture
def production_pack() -> WorkflowPack:
    return WorkflowPack(
        id="production-pack",
        roles=["back", "front", "integration"],
        command_prefixes=["BACK", "FRONT", "INTEG"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank/prod",
        rules_root=".cursor/rules",
        artifact_layout="production-epic-v1",
    )


def test_epic_path_kind_enum():
    """EpicPathKind supports plan, decompose, implement, qa, analyze, audit."""
    assert EpicPathKind.PLAN == "plan"
    assert EpicPathKind.DECOMPOSE == "decompose"
    assert EpicPathKind.IMPLEMENT == "implement"
    assert EpicPathKind.QA == "qa"
    assert EpicPathKind.ANALYZE == "analyze"
    assert EpicPathKind.AUDIT == "audit"


def test_resolve_epic_path_plan_software(tmp_path: Path, software_pack: WorkflowPack):
    """cp1: resolve_epic_path('plan', epic_id, software_pack) → mb_root/back/plan/{epic_id}/md/."""
    epic_id = "T-HUB-050"
    resolved = resolve_epic_path("plan", epic_id, pack=software_pack, cwd=tmp_path)
    expected = tmp_path / "memory-bank" / "back" / "plan" / epic_id / "md"
    assert resolved == expected


def test_resolve_epic_path_plan_video(tmp_path: Path, video_pack: WorkflowPack):
    """cp2: resolve_epic_path('plan', epic_id, video_pack) → memory-bank/video/back/plan/{epic_id}/md/."""
    epic_id = "T-VID-001"
    resolved = resolve_epic_path("plan", epic_id, pack=video_pack, cwd=tmp_path)
    expected = tmp_path / "memory-bank" / "video" / "back" / "plan" / epic_id / "md"
    assert resolved == expected


def test_resolve_epic_path_decompose_subfolder_and_step(tmp_path: Path, software_pack: WorkflowPack):
    """cp3: resolve_epic_path('decompose', ...) → yaml/steps/ subfolder and step file correctly."""
    epic_id = "T-HUB-050"
    # Directory resolution
    dir_resolved = resolve_epic_path("decompose", epic_id, pack=software_pack, cwd=tmp_path)
    assert dir_resolved == tmp_path / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "steps"

    # Step file resolution without slug
    step_resolved = resolve_epic_path(
        "decompose", epic_id, pack=software_pack, step_id="s06", cwd=tmp_path
    )
    assert step_resolved == tmp_path / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "steps" / "s06.yaml"

    # Step file resolution with slug
    step_slug_resolved = resolve_epic_path(
        "decompose", epic_id, pack=software_pack, step_id="s06", step_slug="epic-layout", cwd=tmp_path
    )
    assert step_slug_resolved == tmp_path / "memory-bank" / "back" / "plan" / epic_id / "yaml" / "steps" / "s06-epic-layout.yaml"


def test_resolve_epic_path_implement_matrix(
    tmp_path: Path, software_pack: WorkflowPack, video_pack: WorkflowPack, production_pack: WorkflowPack
):
    """Matrix tests for implement across software, video, and production packs."""
    # Software
    res_sw = resolve_epic_path(
        EpicPathKind.IMPLEMENT, "T-HUB-050", pack=software_pack, step_id="s01", cwd=tmp_path
    )
    assert res_sw == tmp_path / "memory-bank" / "back" / "implement" / "T-HUB-050" / "s01.yaml"

    # Video
    res_vid = resolve_epic_path(
        EpicPathKind.IMPLEMENT, "T-VID-002", pack=video_pack, step_id="s02", step_slug="script", cwd=tmp_path
    )
    assert res_vid == tmp_path / "memory-bank" / "video" / "back" / "implement" / "T-VID-002" / "s02-script.yaml"

    # Production
    res_prod = resolve_epic_path(
        EpicPathKind.IMPLEMENT, "T-PRD-003", pack=production_pack, cwd=tmp_path
    )
    assert res_prod == tmp_path / "memory-bank" / "prod" / "back" / "implement" / "T-PRD-003"


def test_resolve_epic_path_roles(tmp_path: Path, software_pack: WorkflowPack):
    """Role resolution (front, integ/integration)."""
    res_front = resolve_epic_path("plan", "T-HUB-050", pack=software_pack, role="front", cwd=tmp_path)
    assert res_front == tmp_path / "memory-bank" / "front" / "plan" / "T-HUB-050" / "md"

    res_integ = resolve_epic_path("decompose", "T-HUB-050", pack=software_pack, role="integ", cwd=tmp_path)
    assert res_integ == tmp_path / "memory-bank" / "integration" / "plan" / "T-HUB-050" / "yaml" / "steps"


def test_resolve_epic_path_validation_and_errors(tmp_path: Path, software_pack: WorkflowPack):
    """Invalid kind or path traversal fails closed."""
    with pytest.raises(ValueError, match="Unknown EpicPathKind"):
        resolve_epic_path("invalid_kind", "T-HUB-050", pack=software_pack, cwd=tmp_path)

    with pytest.raises(ValueError, match="Invalid characters"):
        resolve_epic_path("plan", "../escape", pack=software_pack, cwd=tmp_path)

    with pytest.raises(ValueError, match="epic_id is required"):
        resolve_epic_path("plan", "", pack=software_pack, cwd=tmp_path)
