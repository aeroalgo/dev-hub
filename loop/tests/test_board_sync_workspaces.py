from __future__ import annotations

from pathlib import Path

import pytest

from loop.board_sync.workspaces import WorkspaceRef, WorkspacesError, discover

FIXTURES = Path(__file__).parent / "fixtures" / "board_sync"


def _valid_workspace_file(tmp_path: Path) -> Path:
    eligible = tmp_path / "eligible"
    (eligible / "memory-bank").mkdir(parents=True)
    no_memory_bank = tmp_path / "no-memory-bank"
    no_memory_bank.mkdir()
    missing = tmp_path / "missing"
    content = (FIXTURES / "workspace_valid.json").read_text(encoding="utf-8")
    content = content.replace("__ELIGIBLE_PATH__", str(eligible))
    content = content.replace("__NO_MEMORY_BANK_PATH__", str(no_memory_bank))
    content = content.replace("__MISSING_PATH__", str(missing))
    workspace_file = tmp_path / "storages" / "workspace.json"
    workspace_file.parent.mkdir()
    workspace_file.write_text(content, encoding="utf-8")
    return workspace_file




def test_discover_eligible(tmp_path: Path) -> None:
    workspace_file = _valid_workspace_file(tmp_path)

    result = discover(tmp_path)

    assert result == [
        WorkspaceRef(path=(tmp_path / "eligible").resolve(), workspace_id="workspace-eligible")
    ]
    assert workspace_file.is_file()


def test_discover_ineligible_skip(tmp_path: Path) -> None:
    _valid_workspace_file(tmp_path)

    result = discover(tmp_path)

    assert all(ref.workspace_id != "workspace-no-memory-bank" for ref in result)


def test_discover_missing_path_skip(tmp_path: Path) -> None:
    _valid_workspace_file(tmp_path)

    result = discover(tmp_path)

    assert all(ref.workspace_id != "workspace-missing" for ref in result)


def test_corrupt_workspace(tmp_path: Path) -> None:
    workspace_file = tmp_path / "storages" / "workspace.json"
    workspace_file.parent.mkdir()
    workspace_file.write_text(
        (FIXTURES / "workspace_corrupt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(WorkspacesError) as exc_info:
        discover(tmp_path)

    assert exc_info.value.diagnostic_code == "workspace_invalid_json"


def test_missing_dsh_home(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(WorkspacesError, match="DSH_HOME does not exist"):
        discover(missing)


def test_workspace_ref_fields(tmp_path: Path) -> None:
    _valid_workspace_file(tmp_path)

    ref = discover(tmp_path)[0]

    assert ref.workspace_id == "workspace-eligible"
    assert ref.path == (tmp_path / "eligible").resolve()
