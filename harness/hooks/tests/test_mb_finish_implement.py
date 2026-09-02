"""Tests for finish_implement_step and CLI mb-finish implement."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.hooks.epic.core import (
    atomic_write_text,
    default_state,
    read_active_context,
    save_epic_state,
)
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.schemas import MbFinishRequest


@pytest.fixture
def setup_epic_env(tmp_path):
    """Set up mock epic environment with decompose, implement, and activeContext."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-TEST"
    mb_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-TEST"
    impl_dir.mkdir(parents=True, exist_ok=True)

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-TEST\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-test.yaml\n"
        "    status: in_progress\n",
        encoding="utf-8",
    )

    s01_decomp = mb_dir / "s01-test.yaml"
    s01_decomp.write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-TEST\n"
        "title: test step\n"
        "next_phase: BACK IMPLEMENT\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: test cp\n",
        encoding="utf-8",
    )

    s01_impl = impl_dir / "s01-test.yaml"
    s01_impl.write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-TEST\n"
        "title: test step\n"
        "status: in_progress\n"
        "date: '2026-09-01'\n"
        "decompose_ref: memory-bank/back/plan/decompose-T-HUB-TEST/s01-test.yaml\n"
        "skills_used: []\n"
        "discovery: []\n"
        "gaps:\n"
        "  status: none\n"
        "done:\n"
        "  - done item\n"
        "files:\n"
        "  - file1.py\n"
        "deletes: []\n"
        "tests:\n"
        "  - '`timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py`'\n"
        "integration_check:\n"
        "  - ok\n"
        "grep_control: []\n"
        "verification_results: []\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: test cp\n"
        "    status: done\n",
        encoding="utf-8",
    )

    act_path = tmp_path / "memory-bank" / "activeContext.md"
    act_content = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-TEST\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "1. [s01-test.yaml](back/plan/decompose-T-HUB-TEST/s01-test.yaml) — test.\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Дальше:** test\n\n"
        "## done\n"
        "- test initial\n"
    )
    act_path.write_text(act_content, encoding="utf-8")

    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": "T-HUB-TEST",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-TEST/index.yaml",
            "armed_step": "s01",
            "armed_role": "BACK",
            "role": "BACK",
        }
    )
    save_epic_state(tmp_path, state)

    return tmp_path


def test_finish_implement_happy(setup_epic_env):
    tmp_path = setup_epic_env

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="finished s01 successfully",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify_check, \
         patch("harness.hooks.epic.core._verify_pass_ready_for_step") as mock_verify_fin:
        mock_verify_check.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_verify_fin.return_value = {"ok": True, "diagnostic": "verify_pass"}

        res = finish_implement_step(req)
        assert res.ok is True
        assert res.diagnostic_codes == []
        assert res.active_context is not None


def test_finish_implement_no_verify(setup_epic_env):
    tmp_path = setup_epic_env

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="trying to finish without verify",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify:
        mock_verify.return_value = {
            "ok": False,
            "error": "verify PASS required before finalize-step",
            "diagnostic": "verify_pass_missing",
        }

        res = finish_implement_step(req)
        assert res.ok is False
        assert "verify_pass_missing" in res.diagnostic_codes

        # Verify SC-001: 0 status mutations in index or implement
        impl_content = (tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-TEST" / "s01-test.yaml").read_text(encoding="utf-8")
        assert "status: in_progress" in impl_content


def test_finish_implement_bad_shape(setup_epic_env):
    tmp_path = setup_epic_env
    original_act = read_active_context(tmp_path)

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="trying bad shape",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify, \
         patch("loop.mb_finish.finish_implement.render_active_context") as mock_render:
        mock_verify.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_render.side_effect = ValueError("rendered activeContext has shape errors: ['missing_load_now']")

        res = finish_implement_step(req)
        assert res.ok is False
        assert "shape_invalid" in res.diagnostic_codes

        # ActiveContext should not be overwritten
        assert read_active_context(tmp_path) == original_act


def test_finish_implement_rollback(setup_epic_env):
    tmp_path = setup_epic_env
    original_act = read_active_context(tmp_path)

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="finish step with forced finalize fail",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify, \
         patch("loop.mb_finish.finish_implement.finalize_step") as mock_fin:
        mock_verify.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_fin.return_value = {"ok": False, "error": "simulated finalize error", "diagnostic": "finalize_failed"}

        res = finish_implement_step(req)
        assert res.ok is False
        assert "finalize_failed" in res.diagnostic_codes

        # Verify activeContext restored
        restored_act = read_active_context(tmp_path)
        assert restored_act == original_act


def test_finish_implement_uses_armed_decompose_not_first_glob(setup_epic_env):
    """Regression: must not finalize the first decompose-* on disk (wrong epic)."""
    tmp_path = setup_epic_env

    stale_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-STALE"
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-HUB-STALE\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-stale.yaml\n"
        "    status: completed\n",
        encoding="utf-8",
    )
    (stale_dir / "s01-stale.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\n",
        encoding="utf-8",
    )

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="finish armed epic only",
        cwd=str(tmp_path),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify, \
         patch("loop.mb_finish.finish_implement.finalize_step") as mock_fin, \
         patch("loop.mb_finish.finish_implement.sync_cursor_from_index") as mock_sync:
        mock_verify.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_fin.return_value = {"ok": True}
        mock_sync.return_value = {"ok": True, "synced": False}

        res = finish_implement_step(req)

    assert res.ok is True
    assert mock_fin.call_count == 1
    decompose_arg = str(mock_fin.call_args.kwargs.get("decompose") or mock_fin.call_args.args[1])
    assert "T-HUB-TEST" in decompose_arg
    assert "T-HUB-STALE" not in decompose_arg


def test_finish_implement_missing_armed_decompose(tmp_path):
    """Fail-closed when epic state has no armed_decompose."""
    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="",
        cwd=str(tmp_path),
    )
    res = finish_implement_step(req)
    assert res.ok is False
    assert "armed_decompose_missing" in res.diagnostic_codes
