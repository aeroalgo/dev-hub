"""Tests for finish_handoff and doctor render reuse (TM-008)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from harness.hooks.epic.core import read_active_context, validate_active_context_shape
from loop.mb_finish.impl import finish_handoff
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta


def test_finish_handoff_valid(tmp_path: Path):
    """cp1: finish_handoff writes valid activeContext via render_active_context."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040",
        step_id="s04",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-040/s04.yaml",
            description="work shard",
        )
    ]
    body = HandoffBody(
        mode="IMPLEMENT",
        next_hint="continue s04",
        epic_id="T-HUB-040",
        step_id="s04",
    )

    res = finish_handoff(meta, load_now, body, cwd=tmp_path)
    assert res.ok is True
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "schema: loop-handoff/v1" in written
    assert "## load_now" in written
    assert "## Handoff BACK IMPLEMENT — s04" in written
    errors = validate_active_context_shape(written)
    assert errors == []


def test_finish_handoff_bad_meta(tmp_path: Path):
    """Bad meta or invalid shape returns MbFinishResult(ok=False)."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040",
        step_id="s04",
    )
    # Empty load_now causing shape validation error in render_active_context
    load_now = []
    body = HandoffBody(
        mode="IMPLEMENT",
        next_hint="continue s04",
    )

    res = finish_handoff(meta, load_now, body, cwd=tmp_path)
    assert res.ok is False
    assert res.diagnostic_codes in (["rendered_shape_invalid"], ["active_context_shape_invalid"], ["render_failed"])


def test_doctor_repair_uses_render(tmp_path: Path):
    """TM-008: doctor repair code path uses render_active_context."""
    with patch("loop.mb_finish.impl.render_active_context") as mock_render:
        mock_render.return_value = "---\nschema: loop-handoff/v1\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-HUB-040\n---\n\n## load_now\n1. [a](a) — b.\n\n## Handoff BACK IMPLEMENT\n- **Дальше:** test\n"
        meta = LoopHandoffMeta(
            role="BACK",
            mode="IMPLEMENT",
            epic_id="T-HUB-040",
            step_id="s04",
        )
        load_now = [LoadNowItem(path="a", description="b")]
        body = HandoffBody(mode="IMPLEMENT", next_hint="test")
        res = finish_handoff(meta, load_now, body, cwd=tmp_path)
        assert mock_render.called
        assert res.ok is True
