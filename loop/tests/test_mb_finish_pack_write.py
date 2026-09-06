"""Tests for mb_finish pack-aware activeContext writing (s05).

Updated in s06 (T-HUB-068): finish_handoff requires recovery_token matching active journal.
Tokenless calls fail-closed.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from loop.mb_finish.impl import finish_handoff, finish_qa, finish_bugfix, finish_decompose, finish_plan
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta, MbFinishRequest
from loop.mb_finish.transaction import FinishTxRecord, FinishTxState, write_finish_tx
from loop.paths.pack_layout import PackLayoutError
from loop.workflow.schemas import WorkflowPack


def test_mb_finish_software_pack_writes_active_context(tmp_path: Path):
    """cp1: mb_finish для software pack -> пишет в memory-bank/activeContext.md."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-050",
        step_id="s05",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-050/s05.yaml",
            description="work shard",
        )
    ]
    body = HandoffBody(
        mode="IMPLEMENT",
        next_hint="continue s05",
        epic_id="T-HUB-050",
        step_id="s05",
    )

    token = "tx-soft-050"
    rec = FinishTxRecord(
        tx_id=token,
        epic_id="T-HUB-050",
        step_id="s05",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        recovery_token=token,
    )
    write_finish_tx(tmp_path, rec)

    res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
    assert res.ok is True
    assert (tmp_path / "memory-bank" / "activeContext.md").exists()
    content = (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8")
    assert "T-HUB-050" in content
    assert not (tmp_path / "memory-bank" / "video" / "activeContext.md").exists()


def test_mb_finish_video_pack_writes_active_context(tmp_path: Path):
    """cp2: mb_finish для video pack -> пишет в memory-bank/video/activeContext.md."""
    (tmp_path / "project.yaml").write_text("workflow_pack: dev-hub-video\n", encoding="utf-8")
    video_pack = WorkflowPack(
        id="dev-hub-video",
        roles=["video", "audio"],
        command_prefixes=["VIDEO", "AUDIO"],
        phase_registry="loop/schemas/phase_registry.yaml",
        memory_bank="memory-bank/video",
        rules_root=".cursor/rules",
        artifact_layout="software-epic-v1",
    )
    video_mb = tmp_path / "memory-bank" / "video"
    video_mb.mkdir(parents=True, exist_ok=True)

    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="V-001",
        step_id="s01",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/video/script/s01.yaml",
            description="script shard",
        )
    ]
    body = HandoffBody(
        mode="IMPLEMENT",
        next_hint="continue s01",
        epic_id="V-001",
        step_id="s01",
    )

    token = "tx-video-001"
    rec = FinishTxRecord(
        tx_id=token,
        epic_id="V-001",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        recovery_token=token,
    )
    write_finish_tx(tmp_path, rec)

    with patch("loop.workflow.registry.get_pack", return_value=video_pack):
        res = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token=token)
        assert res.ok is True
        assert (tmp_path / "memory-bank" / "video" / "activeContext.md").exists()
        content = (tmp_path / "memory-bank" / "video" / "activeContext.md").read_text(encoding="utf-8")
        assert "V-001" in content
        assert not (tmp_path / "memory-bank" / "activeContext.md").exists()


def test_mb_finish_wrong_cwd_fails_closed(tmp_path: Path):
    """cp3: wrong cwd -> fail-closed (PackLayoutError или аналог)."""
    non_existent = tmp_path / "does_not_exist"
    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-050",
        step_id="s05",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-050/s05.yaml",
            description="work shard",
        )
    ]
    body = HandoffBody(
        mode="IMPLEMENT",
        next_hint="continue s05",
    )

    token = "tx-err-050"
    rec = FinishTxRecord(
        tx_id=token,
        epic_id="T-HUB-050",
        step_id="s05",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        recovery_token=token,
    )
    write_finish_tx(non_existent, rec)

    with patch("loop.paths.pack_layout.resolve_workflow_pack") as mock_resolve:
        from loop.workflow.schemas import PackResolveResult
        mock_resolve.return_value = PackResolveResult(
            ok=False,
            pack_id="",
            pack=None,
            diagnostic_codes=["invalid_workflow_pack_registry"],
        )
        with pytest.raises(PackLayoutError):
            finish_handoff(meta, load_now, body, cwd=non_existent, recovery_token=token)
