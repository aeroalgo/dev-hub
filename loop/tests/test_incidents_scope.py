"""Unit tests for loop/incidents/scope.py."""

from pathlib import Path
import json

from loop.incidents.schema import IncidentRecord
from loop.incidents.scope import (
    build_allowlist,
    check_path_allowed,
    write_scope_file,
)


def test_build_allowlist(tmp_path: Path) -> None:
    project_root = tmp_path / "dev-hub"
    project_root.mkdir()

    incident = IncidentRecord(
        incident_id="inc123",
        opened_at="2026-08-30T10:00:00Z",
        project_root=str(project_root),
        epic_id="T-HUB-018",
        step_id="s03",
        phase="BACK IMPLEMENT",
        session_id="sess456",
        source="test",
        diagnostic_codes=["ERR1"],
        fingerprint="fp123",
    )

    allowlist = build_allowlist(incident, project_root)

    expected = [
        str((project_root / "memory-bank" / "activeContext.md").resolve()),
        str((project_root / "memory-bank" / "back" / "plan" / "decompose-T-HUB-018" / "s03").resolve()),
        str((project_root / "memory-bank" / "back" / "implement" / "implement-T-HUB-018" / "s03").resolve()),
        str((project_root / "runtime" / "inc123" / "epic").resolve()),
    ]
    assert sorted(allowlist) == sorted(expected)


def test_path_in_allowlist_returns_true(tmp_path: Path) -> None:
    allowed_file = tmp_path / "allowed.txt"
    allowed_dir = tmp_path / "allowed_dir"
    allowed_dir.mkdir()

    allowlist = [str(allowed_file), str(allowed_dir)]

    assert check_path_allowed(allowed_file, allowlist) is True
    assert check_path_allowed(allowed_dir / "child.txt", allowlist) is True


def test_path_out_of_scope_returns_false(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed_dir"
    allowed_dir.mkdir()

    forbidden_file = tmp_path / "forbidden.txt"
    allowlist = [str(allowed_dir)]

    assert check_path_allowed(forbidden_file, allowlist) is False


def test_path_traversal_returns_false(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed_dir"
    allowed_dir.mkdir()

    traversal_path = allowed_dir / ".." / "forbidden.txt"
    allowlist = [str(allowed_dir)]

    assert check_path_allowed(traversal_path, allowlist) is False


def test_write_scope_file_roundtrip(tmp_path: Path) -> None:
    scope_path = tmp_path / "runtime" / "inc123" / "epic" / "tier1_scope.json"
    allowlist = ["/path/one", "/path/two"]

    write_scope_file(allowlist, scope_path)

    assert scope_path.exists()
    with scope_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("allowlist") == allowlist
