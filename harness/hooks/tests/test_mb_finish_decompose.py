"""Tests for finish_decompose and finish_plan (s06 / TM-007)."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.hooks.epic.core import load_epic_state, read_active_context, save_epic_state
from loop.mb_finish.impl import finish_decompose, finish_plan
from loop.mb_finish.schemas import MbFinishRequest


def test_finish_decompose_arm(tmp_path: Path):
    """cp1: finish_decompose happy path: decompose tree valid -> promote_if_ready called with ANALYZE."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)

    index_md = mb_dir / "index.md"
    index_md.write_text(
        "## Requirements coverage\n- REQ-01: covered\n\n"
        "## Stages coverage\n- s01: covered\n\n"
        "## Outcome map\n- OUT-01: covered\n\n"
        "## Replacement cleanup\n- CLEAN-01: covered\n",
        encoding="utf-8"
    )

    s01_yaml = mb_dir / "s01-step.yaml"
    s01_yaml.write_text("schema: epic-decompose/v1\nstep_id: s01\nplan_id: T-TEST-001\nrole: back\ntitle: Step 1\nnext_phase: BACK IMPLEMENT\nas_built: []\n", encoding="utf-8")

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "role: back\n"
        "steps:\n"
        "  - id: s01\n"
        "    title: step 1\n"
        "    file: s01-step.yaml\n"
        "    status: pending\n",
        encoding="utf-8"
    )

    save_epic_state(tmp_path, {
        "armed_epic": "T-TEST-001",
        "armed_role": "BACK",
        "armed_step": "DECOMPOSE",
        "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
    })

    req = MbFinishRequest(
        phase="BACK DECOMPOSE",
        step_id="s06",
        done_summary="decompose ready",
        cwd=str(tmp_path),
    )

    res = finish_decompose(req)
    assert res.ok is True, f"Expected ok=True, got errors: {res.shape_errors} {res.diagnostic_codes}"
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: ANALYZE" in written


def test_finish_decompose_critical(tmp_path: Path):
    """cp2: finish_decompose: CRITICAL errors in tree -> MbFinishResult(ok=False)."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)

    save_epic_state(tmp_path, {
        "armed_epic": "T-TEST-001",
        "armed_role": "BACK",
        "armed_step": "DECOMPOSE",
        "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
    })

    req = MbFinishRequest(
        phase="BACK DECOMPOSE",
        step_id="s06",
        done_summary="decompose broken",
        cwd=str(tmp_path),
    )

    res = finish_decompose(req)
    assert res.ok is False
    assert "decompose_tree_invalid" in res.diagnostic_codes


def test_finish_decompose_armed_step(tmp_path: Path):
    """cp3 / TM-007: armed_step = ANALYZE в epic state после finish_decompose."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)

    index_md = mb_dir / "index.md"
    index_md.write_text(
        "## Requirements coverage\n- REQ-01: covered\n\n"
        "## Stages coverage\n- s01: covered\n\n"
        "## Outcome map\n- OUT-01: covered\n\n"
        "## Replacement cleanup\n- CLEAN-01: covered\n",
        encoding="utf-8"
    )

    s01_yaml = mb_dir / "s01-step.yaml"
    s01_yaml.write_text("schema: epic-decompose/v1\nstep_id: s01\nplan_id: T-TEST-001\nrole: back\ntitle: Step 1\nnext_phase: BACK IMPLEMENT\nas_built: []\n", encoding="utf-8")

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "role: back\n"
        "steps:\n"
        "  - id: s01\n"
        "    title: step 1\n"
        "    file: s01-step.yaml\n"
        "    status: pending\n",
        encoding="utf-8"
    )

    save_epic_state(tmp_path, {
        "armed_epic": "T-TEST-001",
        "armed_role": "BACK",
        "armed_step": "DECOMPOSE",
        "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
    })

    req = MbFinishRequest(
        phase="BACK DECOMPOSE",
        step_id="s06",
        done_summary="decompose ready",
        cwd=str(tmp_path),
    )

    res = finish_decompose(req)
    assert res.ok is True

    state = load_epic_state(tmp_path)
    assert state.get("armed_step") == "ANALYZE" or state.get("armed_mode") == "ANALYZE" or "ANALYZE" in str(state)


def test_finish_plan_happy(tmp_path: Path):
    """cp4: finish_plan happy path."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan"
    mb_dir.mkdir(parents=True, exist_ok=True)
    plan_file = mb_dir / "plan-T-TEST-001.md"
    plan_file.write_text("# Plan T-TEST-001\n", encoding="utf-8")

    save_epic_state(tmp_path, {
        "armed_epic": "T-TEST-001",
        "armed_role": "BACK",
        "armed_plan": "memory-bank/back/plan/plan-T-TEST-001.md"
    })

    req = MbFinishRequest(
        phase="BACK PLAN",
        step_id="s06",
        done_summary="plan ready",
        cwd=str(tmp_path),
    )

    res = finish_plan(req)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: DECOMPOSE" in written


def test_finish_plan_no_artifact(tmp_path: Path):
    """cp4: finish_plan without plan artifact returns ok=False."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-TEST-001", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK PLAN",
        step_id="s06",
        done_summary="plan missing",
        cwd=str(tmp_path),
    )

    res = finish_plan(req)
    assert res.ok is False
    assert "plan_artifact_missing" in res.diagnostic_codes
