from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from loop.board_sync.card_model import CardKind, parse_metadata
from loop.board_sync.client import FakeClient
from loop.board_sync.diff import BoardTask, work_item_card
from loop.board_sync.scan_mb import WorkItem
from loop.board_sync.sync import run_sync
from loop.board_sync.workspaces import WorkspaceRef
from .test_board_sync_sync import _card, _project


def test_e2e_pending_steps_emit_single_epic_card_pending_to_epic(tmp_path: Path) -> None:
    ref = _project(tmp_path, statuses=["pending"] * 12)
    client = FakeClient()

    res = run_sync([ref], client)

    assert res.errors == ()
    assert client.write_count >= 1

    epics = [c for c in client.tasks.values() if parse_metadata(c.description).card_kind == CardKind.EPIC]
    steps = [c for c in client.tasks.values() if parse_metadata(c.description).card_kind == CardKind.STEP]

    assert len(epics) == 1
    assert len(steps) == 0


def test_e2e_arm_epic_decompose_sets_handoff_arm_decompose_handoff(tmp_path: Path) -> None:
    from loop.context_loop import arm_epic

    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    active_ctx = mb / "activeContext.md"
    active_ctx.write_text("## load_now\nold content\n", encoding="utf-8")

    plan_dir = mb / "back/plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("# Plan T-HUB-TEST\n", encoding="utf-8")

    res = arm_epic(
        cwd=tmp_path,
        epic_id="T-HUB-TEST",
        role="back",
    )

    assert res["ok"] is True
    content = active_ctx.read_text(encoding="utf-8")
    assert "DECOMPOSE" in content
    assert "plan-T-HUB-TEST.md" in content


def test_e2e_arm_epic_implement_sets_step(tmp_path: Path) -> None:
    from loop.context_loop import arm_epic

    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    active_ctx = mb / "activeContext.md"
    active_ctx.write_text("## load_now\nold content\n", encoding="utf-8")

    plan_dir = mb / "back/plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("# Plan T-HUB-TEST\n", encoding="utf-8")

    index_dir = plan_dir / "decompose-T-HUB-TEST"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "index.md").write_text("# index md", encoding="utf-8")
    (index_dir / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": "T-HUB-TEST",
                "steps": [
                    {"id": "s01", "title": "step 1", "status": "completed"},
                    {"id": "s02", "title": "step 2", "status": "completed"},
                    {"id": "s03", "title": "step 3", "status": "pending", "file": "s03.yaml"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (index_dir / "s03.yaml").write_text("schema: epic-decompose/v1\ntitle: step 3\n", encoding="utf-8")

    res = arm_epic(
        cwd=tmp_path,
        epic_id="T-HUB-TEST",
        role="back",
    )

    assert res["ok"] is True
    assert res["step_id"] == "s03"
    content = active_ctx.read_text(encoding="utf-8")
    assert "IMPLEMENT" in content
    assert "s03.yaml" in content


def test_e2e_sync_roadmap_rank_column_running_backlog_roadmap_column(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank/back/plan"
    mb.mkdir(parents=True, exist_ok=True)

    queue_data = {
        "version": "roadmap-queue/v1",
        "role": "back",
        "queue": [
            {"id": "T-EPIC-1", "plan": "plan-T-EPIC-1.md", "deps": []},
            {"id": "T-EPIC-2", "plan": "plan-T-EPIC-2.md", "deps": []},
        ],
    }
    (tmp_path / "memory-bank/back/roadmap-back.queue.yaml").write_text(
        yaml.safe_dump(queue_data), encoding="utf-8"
    )

    for ep in ["T-EPIC-1", "T-EPIC-2"]:
        (mb / f"plan-{ep}.md").write_text(f"# {ep}\n", encoding="utf-8")
        idx = mb / f"decompose-{ep}/index.yaml"
        idx.parent.mkdir(parents=True, exist_ok=True)
        (idx.parent / "index.md").write_text("# index md", encoding="utf-8")
        idx.write_text(
            yaml.safe_dump(
                {
                    "schema": "epic-decompose-index/v1",
                    "plan_id": ep,
                    "steps": [{"id": "s01", "title": "step 1", "status": "in_progress" if ep == "T-EPIC-1" else "pending"}],
                }
            ),
            encoding="utf-8",
        )

    ref = WorkspaceRef(tmp_path, "ws1")

    old_step_item = WorkItem(
        role="back",
        epic_id="T-EPIC-1",
        step_id="s01",
        status="pending",
        decompose_rel="memory-bank/back/plan/decompose-T-EPIC-1/index.yaml",
        title="s01",
        workspace_ref=ref,
    )
    step_card = work_item_card(old_step_item, sync_generation=1)
    client = FakeClient([step_card])

    res = run_sync([ref], client)

    assert res.errors == ()
    assert step_card.id in client.archived

    card1 = client.tasks["mb-ws1-back-t-epic-1-epic"]
    card2 = client.tasks["mb-ws1-back-t-epic-2-epic"]

    assert card1.status == "running"
    assert card2.status == "backlog"


def test_e2e_step_era_cards_archived_on_sync(tmp_path: Path) -> None:
    ref = _project(tmp_path, statuses=["pending"])
    old_card = _card(ref, "T-DEMO", "s01")
    client = FakeClient([old_card])

    run_sync([ref], client)
    assert old_card.id in client.archived


def test_e2e_epic_done_maps_to_todo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loop.board_sync.epic_resolver import EpicNextAction

    ref = _project(tmp_path, statuses=["completed"])

    done_action = EpicNextAction(
        epic_id="T-DEMO",
        role="back",
        next_command="BACK DECOMPOSE T-DEMO",
        phase="DONE",
        reason_code="epic_completed",
    )

    monkeypatch.setattr(
        "loop.board_sync.scan_epics.resolve_epic_next_action",
        lambda *args, **kwargs: done_action,
    )

    client = FakeClient()
    run_sync([ref], client)

    card = next(c for c in client.tasks.values() if parse_metadata(c.description).card_kind == CardKind.EPIC)
    assert card.status == "todo"
