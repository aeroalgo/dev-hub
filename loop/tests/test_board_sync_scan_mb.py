from __future__ import annotations

from pathlib import Path

import yaml

from loop.board_sync.scan_mb import WorkItem, scan_steps
from loop.board_sync.workspaces import WorkspaceRef

FIXTURES = Path(__file__).parent / "fixtures" / "board_sync"


def _fixture_ref() -> WorkspaceRef:
    return WorkspaceRef(
        path=(FIXTURES / "mini_mb_project").resolve(),
        workspace_id="mini-workspace",
    )


def test_scan_steps_filters_status() -> None:
    result = scan_steps([_fixture_ref()])

    assert all(item.status in {"pending", "in_progress", "active", "blocked"} for item in result)
    assert {item.step_id for item in result} == {"s01", "s02", "s03"}
    assert all(item.step_id != "s04" for item in result)


def test_scan_steps_count() -> None:
    result = scan_steps([_fixture_ref()])

    assert len(result) == 3
    assert sum(item.status == "pending" for item in result) == 2
    assert sum(item.status == "in_progress" for item in result) == 1


def test_corrupt_index_skip(tmp_path: Path) -> None:
    valid = tmp_path / "valid"
    valid_index = valid / "memory-bank" / "back" / "plan" / "decompose-T-VALID/index.yaml"
    valid_index.parent.mkdir(parents=True)
    valid_index.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": "T-VALID",
                "steps": [{"id": "s01", "title": "Valid", "status": "pending"}],
            }
        ),
        encoding="utf-8",
    )
    corrupt = tmp_path / "corrupt"
    corrupt_index = corrupt / "memory-bank" / "back" / "plan" / "decompose-T-CORRUPT/index.yaml"
    corrupt_index.parent.mkdir(parents=True)
    corrupt_index.write_text("schema: [not valid", encoding="utf-8")

    result = scan_steps(
        [
            WorkspaceRef(valid, "valid"),
            WorkspaceRef(corrupt, "corrupt"),
        ]
    )

    assert [item.epic_id for item in result] == ["T-VALID"]
    assert result.errors
    assert "T-CORRUPT" in result.errors[0]


def test_missing_memory_bank_skip(tmp_path: Path) -> None:
    result = scan_steps([WorkspaceRef(tmp_path / "missing", "missing")])

    assert result == []
    assert result.errors == []


def test_multi_role(tmp_path: Path) -> None:
    project = tmp_path / "project"
    for role in ("back", "front"):
        index = project / "memory-bank" / role / "plan" / f"decompose-T-{role.upper()}/index.yaml"
        index.parent.mkdir(parents=True)
        index.write_text(
            yaml.safe_dump(
                {
                    "schema": "epic-decompose-index/v1",
                    "plan_id": f"T-{role.upper()}",
                    "steps": [{"id": "s01", "title": role, "status": "pending"}],
                }
            ),
            encoding="utf-8",
        )

    result = scan_steps([WorkspaceRef(project, "multi")])

    assert {item.role for item in result} == {"back", "front"}
    assert {item.title for item in result} == {"back", "front"}


def test_workitem_fields() -> None:
    item = scan_steps([_fixture_ref()])[0]

    assert isinstance(item, WorkItem)
    assert item.decompose_rel == (
        "memory-bank/back/plan/decompose-T-HUB-007-test/index.yaml"
    )
    assert item.epic_id == "T-HUB-007-test"
    assert item.step_id == "s01"
    assert item.title == "First pending"
    assert item.workspace_ref == _fixture_ref()
