"""Tests for finish_handoff and doctor render reuse (TM-008)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from harness.hooks.epic.core import read_active_context, validate_active_context_shape
from loop.mb_finish.impl import finish_handoff
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
from loop.mb_finish.transaction import FinishTxRecord, FinishTxState, write_finish_tx


def _prepare_tx(tmp_path: Path, epic_id: str, step_id: str, token: str = "tx-token-test") -> str:
    rec = FinishTxRecord(
        tx_id=token,
        epic_id=epic_id,
        step_id=step_id,
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        recovery_token=token,
    )
    write_finish_tx(tmp_path, rec)
    return token


def test_finish_handoff_valid(tmp_path: Path):
    """cp1: finish_handoff writes valid activeContext via render_active_context."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    token = _prepare_tx(tmp_path, "T-HUB-040", "s04")

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

    res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
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

    token = _prepare_tx(tmp_path, "T-HUB-040", "s04")

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

    res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
    assert res.ok is False
    assert res.diagnostic_codes in (["rendered_shape_invalid"], ["active_context_shape_invalid"], ["render_failed"])


@pytest.mark.parametrize("target_mode", ["DONE", "IMPLEMENT", "ANALYZE", "DECOMPOSE", "PLAN", "QA"])
def test_finish_handoff_qa_fail_blocks_handoff_gate(tmp_path: Path, target_mode: str):
    """cp3 / FR-003 / US-003 / SC-003: finish_handoff with latest qa fail blocks non-BUGFIX modes with qa_fail_blocks_handoff."""
    epic = "T-HUB-040"
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / epic
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "qa-001.yaml").write_text("verdict: fail\nepic_id: T-HUB-040\n", encoding="utf-8")

    from harness.hooks.epic.core import save_epic_state
    save_epic_state(tmp_path, {"armed_epic": epic, "armed_role": "BACK"})

    token = _prepare_tx(tmp_path, epic, "s04")
    meta = LoopHandoffMeta(
        role="BACK",
        mode=target_mode,
        epic_id=epic,
    )
    load_now = [
        LoadNowItem(path="memory-bank/back/plan/decompose-T-HUB-040/s04.yaml", description="work shard")
    ]
    body = HandoffBody(
        mode=target_mode,
        next_hint=f"continue {target_mode}",
        epic_id=epic,
    )

    res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
    assert res.ok is False
    assert "qa_fail_blocks_handoff" in (res.diagnostic_codes or [])



def test_doctor_repair_uses_render(tmp_path: Path):
    """TM-008: doctor repair code path uses render_active_context."""
    token = _prepare_tx(tmp_path, "T-HUB-040", "s04")
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
        res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
        assert mock_render.called
        assert res.ok is True

