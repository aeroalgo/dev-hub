from __future__ import annotations

from pathlib import Path
import pytest

from loop.kernel.index import (
    EpicKind,
    SUPPORTED_KINDS,
    discover_epic_kinds,
    execute_path,
    implement_path,
    index_path,
    normalize_kind,
    plan_path,
    plan_root,
    resolve_epic_kind,
    resolve_epic_role,
    Step,
)
from loop.kernel.model import Cursor


def test_discover_and_path_resolution(tmp_path: Path) -> None:
    # Cursor.kind field and persistence
    cursor = Cursor(epic_id="EPIC-1", role="back", kind="security")
    assert cursor.kind == "security"
    dumped = cursor.to_dict()
    assert dumped["kind"] == "security"
    restored = Cursor.from_dict(dumped)
    assert restored.kind == "security"

    # Default kind
    default_cursor = Cursor(epic_id="EPIC-1")
    assert default_cursor.kind == "feature"
    assert default_cursor.to_dict()["kind"] == "feature"

    # Supported kinds
    assert set(SUPPORTED_KINDS) == {"feature", "refactor", "security"}
    assert normalize_kind("SECURITY") == "security"
    assert normalize_kind(None) == "feature"
    with pytest.raises(ValueError, match="unsupported kind"):
        normalize_kind("unknown")

    # plan_root helper
    assert plan_root("feature") == Path("plan")
    assert plan_root("refactor") == Path("refactor/plan")
    assert plan_root("security") == Path("security/plan")
    assert plan_root(tmp_path, "back", "security") == tmp_path / "memory-bank" / "back" / "security" / "plan"

    # Path helpers
    assert index_path(tmp_path, "back", "EPIC-1", kind="security") == (
        tmp_path / "memory-bank" / "back" / "security" / "plan" / "EPIC-1" / "yaml" / "decompose-index.yaml"
    )
    assert plan_path(tmp_path, "back", "EPIC-1", kind="security") == (
        tmp_path / "memory-bank" / "back" / "security" / "plan" / "EPIC-1" / "md" / "plan.md"
    )
    assert execute_path(tmp_path, "back", "EPIC-1", "s01", kind="security") == (
        tmp_path / "memory-bank" / "back" / "security" / "implement" / "EPIC-1" / "s01.yaml"
    )
    step = Step(step_id="s01", status="pending", title="Step 1", shard="s01-shard.yaml")
    assert implement_path(tmp_path, "back", "EPIC-1", step, kind="security") == (
        tmp_path / "memory-bank" / "back" / "security" / "implement" / "EPIC-1" / "s01-shard.yaml"
    )

    # discover_epic_kinds
    sec_plan = plan_path(tmp_path, "back", "EPIC-SEC", kind="security")
    sec_plan.parent.mkdir(parents=True, exist_ok=True)
    sec_plan.write_text("# Security Plan\n", encoding="utf-8")

    assert discover_epic_kinds(tmp_path, "EPIC-SEC") == ["security"]
    assert discover_epic_kinds(tmp_path, "EPIC-SEC", role="back") == ["security"]
    assert discover_epic_kinds(tmp_path, "EPIC-SEC", role="front") == []


def test_security_kind_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as exc_info:
        resolve_epic_role(tmp_path, "NON-EXISTENT")
    err = str(exc_info.value)
    assert "searched roots" in err
    assert "memory-bank/back/plan/NON-EXISTENT/md/plan.md" in err
    assert "memory-bank/back/security/plan/NON-EXISTENT/md/plan.md" in err
    assert "memory-bank/back/refactor/plan/NON-EXISTENT/md/plan.md" in err


def test_security_kind_ambiguous(tmp_path: Path) -> None:
    feat_plan = plan_path(tmp_path, "back", "AMBIG-1", kind="feature")
    feat_plan.parent.mkdir(parents=True, exist_ok=True)
    feat_plan.write_text("# Feature Plan\n", encoding="utf-8")

    sec_plan = plan_path(tmp_path, "back", "AMBIG-1", kind="security")
    sec_plan.parent.mkdir(parents=True, exist_ok=True)
    sec_plan.write_text("# Security Plan\n", encoding="utf-8")

    # Ambiguous without --kind -> fail-closed
    with pytest.raises(ValueError, match="ambiguous.*--kind"):
        resolve_epic_role(tmp_path, "AMBIG-1")

    # Disambiguated by kind
    assert resolve_epic_role(tmp_path, "AMBIG-1", kind="security") == "back"
    assert resolve_epic_role(tmp_path, "AMBIG-1", kind="feature") == "back"
    assert resolve_epic_kind(tmp_path, "AMBIG-1", kind="security") == "security"


def test_refactor_kind_path(tmp_path: Path) -> None:
    ref_plan = plan_path(tmp_path, "front", "REF-1", kind="refactor")
    ref_plan.parent.mkdir(parents=True, exist_ok=True)
    ref_plan.write_text("# Refactor Plan\n", encoding="utf-8")

    assert discover_epic_kinds(tmp_path, "REF-1") == ["refactor"]
    assert resolve_epic_role(tmp_path, "REF-1") == "front"
    assert resolve_epic_kind(tmp_path, "REF-1") == "refactor"

    idx = index_path(tmp_path, "front", "REF-1", kind="refactor")
    assert "front/refactor/plan/REF-1/yaml/decompose-index.yaml" in idx.as_posix()

    step = Step(step_id="s01", status="pending", title="Refactor Step 1", shard=None)
    exec_p = execute_path(tmp_path, "front", "REF-1", step, kind="refactor")
    assert "front/refactor/implement/REF-1/s01.yaml" in exec_p.as_posix()


def test_cli_parser_kind_argument() -> None:
    from loop.kernel.cli import _parser

    parser = _parser()
    args = parser.parse_args(["start", "--epic", "SEC-EPIC", "--kind", "security"])
    assert args.kind == "security"

    args_default = parser.parse_args(["start", "--epic", "FEAT-EPIC"])
    assert args_default.kind is None

    with pytest.raises(SystemExit):
        parser.parse_args(["start", "--epic", "SEC-EPIC", "--kind", "invalid-kind"])
