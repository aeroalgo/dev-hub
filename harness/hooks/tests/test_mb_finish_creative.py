"""Tests for finish_creative and finish_reflect (s08 / TM-008)."""

import sys
from pathlib import Path
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.hooks.epic.core import save_epic_state
from loop.mb_finish.impl import (
    finish_analyze,
    finish_audit,
    finish_bugfix,
    finish_creative,
    finish_decompose,
    finish_plan,
    finish_qa,
    finish_reflect,
)
from loop.mb_finish.schemas import MbFinishRequest, MbFinishResult


def test_finish_creative_happy(tmp_path: Path):
    """cp1: finish_creative happy path -> ok=True, mode=IMPLEMENT."""
    mb_dir = tmp_path / "memory-bank" / "back" / "creative"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "creative-T-HUB-040.md").write_text("# Creative\nDesign details", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040-harness-workflow-finish-api",
            "armed_role": "BACK",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml",
        },
    )

    req = MbFinishRequest(
        phase="BACK CREATIVE",
        step_id="s08",
        done_summary="creative finished",
        cwd=str(tmp_path),
    )

    res = finish_creative(req)
    assert res.ok is True, f"Expected ok=True, got: {res.shape_errors} {res.diagnostic_codes}"
    assert "activeContext.md" in res.active_context or "IMPLEMENT" in res.active_context
    assert (tmp_path / "memory-bank" / "activeContext.md").is_file()


def test_finish_creative_no_artifact(tmp_path: Path):
    """finish_creative when creative artifact is missing."""
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040-harness-workflow-finish-api",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK CREATIVE",
        step_id="s08",
        done_summary="creative finished",
        cwd=str(tmp_path),
    )

    res = finish_creative(req)
    assert res.ok is False
    assert "creative_artifact_missing" in res.diagnostic_codes


def test_finish_reflect_happy(tmp_path: Path):
    """cp2: finish_reflect happy path -> ok=True."""
    mb_dir = tmp_path / "memory-bank" / "back" / "reflection"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "reflection-T-HUB-040.md").write_text("# Reflection\nLessons learned", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040-harness-workflow-finish-api",
            "armed_role": "BACK",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml",
        },
    )

    req = MbFinishRequest(
        phase="BACK REFLECT",
        step_id="s08",
        done_summary="reflection finished",
        cwd=str(tmp_path),
    )

    res = finish_reflect(req)
    assert res.ok is True, f"Expected ok=True, got: {res.shape_errors} {res.diagnostic_codes}"
    assert (tmp_path / "memory-bank" / "activeContext.md").is_file()


def test_finish_reflect_no_artifact(tmp_path: Path):
    """finish_reflect when reflection artifact is missing."""
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-040-harness-workflow-finish-api",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK REFLECT",
        step_id="s08",
        done_summary="reflection finished",
        cwd=str(tmp_path),
    )

    res = finish_reflect(req)
    assert res.ok is False
    assert "reflection_artifact_missing" in res.diagnostic_codes


@pytest.mark.parametrize(
    "fn",
    [
        finish_analyze,
        finish_audit,
        finish_qa,
        finish_bugfix,
        finish_decompose,
        finish_plan,
        finish_creative,
        finish_reflect,
    ],
)
def test_uniform_contract_matrix(tmp_path: Path, fn):
    """cp3: matrix test: все phase tools возвращают MbFinishResult с полями ok + diagnostic_codes."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    req = MbFinishRequest(
        phase="BACK TEST",
        step_id="s08",
        done_summary="test matrix",
        cwd=str(tmp_path),
    )

    res = fn(req)
    assert isinstance(res, MbFinishResult)
    assert isinstance(res.ok, bool)
    assert isinstance(res.diagnostic_codes, list)
    assert hasattr(res, "shape_errors")
    assert hasattr(res, "active_context")
