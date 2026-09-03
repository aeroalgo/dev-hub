from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loop.board_sync.card_model import parse_metadata
from loop.board_sync.client import FakeClient
from loop.board_sync.diff import BoardTask, work_item_card
from loop.board_sync.scan_mb import WorkItem
from loop.board_sync.sync import run_sync
from loop.board_sync.workspaces import WorkspaceRef


def _card(ref: WorkspaceRef, epic: str, step: str) -> BoardTask:
    item = WorkItem(
        role="back",
        epic_id=epic,
        step_id=step,
        status="pending",
        decompose_rel=f"memory-bank/back/plan/decompose-{epic}/index.yaml",
        title=step,
        workspace_ref=ref,
    )
    return work_item_card(item, sync_generation=1)


def _set_status(ref: WorkspaceRef, epic: str, statuses: list[str]) -> None:
    ref.path.joinpath(
        f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    ).write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic,
                "steps": [
                    {"id": f"s{i:02d}", "title": "step", "status": status}
                    for i, status in enumerate(statuses, 1)
                ],
            }
        ),
        encoding="utf-8",
    )


def _done_reducer(*_: object) -> dict[str, str]:
    return {"phase": "DONE", "reason_code": "reflection_completed"}


@pytest.fixture
def done_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("loop.board_sync.scan_gates.reduce_epic_lifecycle", _done_reducer)


def _project(tmp_path: Path, *, statuses: list[str], epic: str = "T-DEMO") -> WorkspaceRef:
    index = tmp_path / "memory-bank/back/plan" / f"decompose-{epic}/index.yaml"
    index.parent.mkdir(parents=True)
    index.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": epic,
                "steps": [
                    {"id": f"s{i:02d}", "title": "step", "status": status}
                    for i, status in enumerate(statuses, 1)
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "memory-bank/back/plan/plan-T-DEMO.md").write_text(
        "# T-DEMO\n", encoding="utf-8"
    )
    (tmp_path / "memory-bank/back/plan/roadmap-epics.queue.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "roadmap-queue/v1",
                "role": "back",
                "queue": [
                    {"id": "T-DEMO", "plan": "plan-T-DEMO.md", "deps": []}
                ],
            }
        ),
        encoding="utf-8",
    )
    return WorkspaceRef(tmp_path, "demo")


def test_fake_client() -> None:
    client = FakeClient()
    assert client.list_tasks() == []
    from loop.board_sync.diff import BoardTask

    card = BoardTask("mb-demo", "title", "description", "prompt")
    client.upsert(card)
    client.archive(card.id)

    assert client.list_tasks() == [card]
    assert client.archived == {card.id}
    assert client.write_count == 2


def test_dry_run_no_writes(tmp_path: Path) -> None:
    client = FakeClient()
    run_sync([_project(tmp_path, statuses=["pending"])], client, dry_run=True)

    assert client.write_count == 0


def test_roadmap_selection_failure_is_reported_without_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ref = _project(tmp_path, statuses=["completed"])
    monkeypatch.setattr(
        "roadmap_queue.select_next_epic",
        lambda *_: {"ok": False, "error": "queue_yaml_missing"},
    )
    client = FakeClient()

    result = run_sync([ref], client)

    assert result.errors == (f"{ref.path}: roadmap selection failed: queue_yaml_missing",)
    assert result.operations == ()
    assert client.write_count == 0


def test_obsolete_step_card_deleted_on_epic_sync(tmp_path: Path) -> None:
    ref = _project(tmp_path, statuses=["pending"])
    old_step = _card(ref, "T-DEMO", "s01")
    client = FakeClient([old_step])

    result = run_sync([ref], client)

    assert old_step.id in client.archived
    assert any(task.id.endswith("-epic") for task in client.tasks.values())
    assert any(operation.kind == "archive" for operation in result.operations)


def test_done_epic_archive_all(
    tmp_path: Path, done_lifecycle: None
) -> None:
    ref = _project(tmp_path, statuses=["completed", "done"])
    client = FakeClient(
        [
            _card(ref, "T-DEMO", "s01"),
            _card(ref, "T-DEMO", "s02"),
            _card(ref, "T-OTHER", "s01"),
            BoardTask("manual-1", "Keep", "manual", ""),
        ]
    )

    result = run_sync([ref], client)

    assert result.archived == 3
    assert client.archived == {
        "mb-demo-back-t-demo-s01",
        "mb-demo-back-t-demo-s02",
        "mb-demo-back-t-other-s01",
    }


def test_done_epic_preserves_unrelated_cards(
    tmp_path: Path, done_lifecycle: None
) -> None:
    ref = _project(tmp_path, statuses=["completed"])
    other = _card(ref, "T-OTHER", "s01")
    manual = BoardTask("manual-1", "Keep", "manual", "")
    client = FakeClient([other, manual])

    result = run_sync([ref], client)

    assert result.archived == 1
    assert client.archived == {other.id}
    assert client.tasks[manual.id] == manual


def test_non_mb_preserved(tmp_path: Path) -> None:
    from loop.board_sync.diff import BoardTask

    manual = BoardTask("manual-1", "Keep", "manual", "")
    client = FakeClient([manual])
    run_sync([_project(tmp_path, statuses=["pending"])], client)

    assert client.tasks[manual.id] == manual
    assert manual.id not in client.archived


def test_sync_generation_increment(tmp_path: Path) -> None:
    ref = _project(tmp_path, statuses=["pending"])
    client = FakeClient()
    first = run_sync([ref], client)
    second = run_sync([ref], client)

    assert first.sync_generation == 1
    assert second.sync_generation == 2
    assert second.operations == ()
    assert client.write_count >= 1
    assert parse_metadata(client.tasks[next(iter(client.tasks))].description).sync_generation == 1
