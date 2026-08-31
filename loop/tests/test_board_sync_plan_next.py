import pytest
from pathlib import Path
from loop.board_sync.plan_next import (
    EpicNextOverride,
    parse_plan_next,
    write_plan_next,
    validate_plan_next,
)

def test_parse_plan_next_returns_override_from_footer(tmp_path: Path):
    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text(
        "# Plan Title\n"
        "Some plan description.\n"
        "---\n"
        "plan-next/v1:\n"
        "  epic_id: T-TEST-001\n"
        "  role: back\n"
        "  next_command: BACK DECOMPOSE T-TEST-001\n"
    )

    override = parse_plan_next(plan_file)
    assert override is not None
    assert override.epic_id == "T-TEST-001"
    assert override.role == "back"
    assert override.next_command == "BACK DECOMPOSE T-TEST-001"

def test_parse_plan_next_none_if_no_footer(tmp_path: Path):
    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text("# Plan Title\nNo footer here.")

    assert parse_plan_next(plan_file) is None

def test_parse_plan_next_none_if_no_plan_next_key(tmp_path: Path):
    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text(
        "# Plan Title\n"
        "---\n"
        "other-key: value\n"
    )

    assert parse_plan_next(plan_file) is None

def test_write_plan_next_appends_yaml_block(tmp_path: Path):
    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text("# Plan Title\nSome content.")

    override = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK DECOMPOSE T-TEST-001"
    )
    write_plan_next(plan_file, override)

    parsed = parse_plan_next(plan_file)
    assert parsed == override
    content = plan_file.read_text()
    assert "---\nplan-next/v1:" in content

def test_write_plan_next_idempotent_on_second_write(tmp_path: Path):
    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text("# Plan Title\nSome content.")

    override = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK DECOMPOSE T-TEST-001"
    )
    write_plan_next(plan_file, override)
    content_first = plan_file.read_text()

    # Second write with same content
    write_plan_next(plan_file, override)
    content_second = plan_file.read_text()

    assert content_first == content_second

    # Second write with updated next_command
    override_updated = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK IMPLEMENT s01"
    )
    write_plan_next(plan_file, override_updated)
    parsed = parse_plan_next(plan_file)
    assert parsed == override_updated

def test_validate_plan_next_valid_override():
    override = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK DECOMPOSE T-TEST-001"
    )
    diag = validate_plan_next(override, {"plan_exists": True})
    assert diag is None

def test_validate_plan_next_conflict_decompose_missing_plan():
    override = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK DECOMPOSE T-TEST-001"
    )
    diag = validate_plan_next(override, {"plan_exists": False})
    assert diag is not None
    assert "plan file does not exist" in diag

def test_plan_finish_hook_writes_plan_next(tmp_path: Path):
    from loop.board_sync.plan_next import parse_plan_next, write_plan_next, EpicNextOverride

    plan_file = tmp_path / "plan-T-TEST-001.md"
    plan_file.write_text("# Plan\nContent\n")

    override = EpicNextOverride(
        epic_id="T-TEST-001",
        role="back",
        next_command="BACK DECOMPOSE T-TEST-001"
    )
    write_plan_next(plan_file, override)

    res = parse_plan_next(plan_file)
    assert res == override
