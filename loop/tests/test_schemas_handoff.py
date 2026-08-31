"""Tests for LoopHandoffFrontmatter and active_context frontmatter functions."""

import pytest
from pydantic import ValidationError

from loop.schemas.active_context import (
    handoff_mode_from_text,
    parse_handoff_meta,
    render_with_frontmatter,
    split_frontmatter,
    validate_handoff_frontmatter,
)
from loop.schemas.handoff import SCHEMA_LOOP_HANDOFF, LoopHandoffFrontmatter


def test_parse_valid_frontmatter():
    text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-022\n"
        "step_id: s07\n"
        "---\n\n"
        "## load_now\n"
    )
    meta = parse_handoff_meta(text)
    assert meta is not None
    assert meta.schema_version == SCHEMA_LOOP_HANDOFF
    assert meta.role == "BACK"
    assert meta.mode == "IMPLEMENT"
    assert meta.epic_id == "T-HUB-022"
    assert meta.step_id == "s07"


def test_parse_legacy_no_frontmatter():
    text = "## load_now\n1. [s07.yaml](...)\n\n## Handoff BACK IMPLEMENT\n"
    assert parse_handoff_meta(text) is None
    parsed, body = split_frontmatter(text)
    assert parsed is None
    assert body == text


def test_invalid_role():
    with pytest.raises(ValidationError):
        LoopHandoffFrontmatter(
            schema="loop-handoff/v1",
            role="INVALID_ROLE",  # type: ignore
            mode="IMPLEMENT",
            epic_id="T-HUB-022",
        )


def test_mode_uppercase_coercion():
    meta = LoopHandoffFrontmatter(
        schema="loop-handoff/v1",
        role="back",  # type: ignore
        mode="implement",
        epic_id="T-HUB-022",
    )
    assert meta.role == "BACK"
    assert meta.mode == "IMPLEMENT"


def test_integration_role_coercion():
    meta = LoopHandoffFrontmatter(
        schema="loop-handoff/v1",
        role="integration",  # type: ignore
        mode="IMPLEMENT",
        epic_id="T-HUB-022",
    )
    assert meta.role == "INTEG"


def test_round_trip_dump_parse():
    original = LoopHandoffFrontmatter(
        schema="loop-handoff/v1",
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-022",
        step_id="s07",
        reason_code="REASON_1",
        projection_hash="abc123hash",
    )
    body = "## load_now\nsome content"
    rendered = render_with_frontmatter(body, original)

    meta, errors = validate_handoff_frontmatter(rendered)
    assert not errors
    assert meta is not None
    assert meta.schema_version == original.schema_version
    assert meta.role == original.role
    assert meta.mode == original.mode
    assert meta.epic_id == original.epic_id
    assert meta.step_id == original.step_id
    assert meta.reason_code == original.reason_code
    assert meta.projection_hash == original.projection_hash


def test_extract_handoff_phase_heading():
    legacy_text = (
        "## load_now\n"
        "1. [s07.yaml](...)\n\n"
        "## Handoff BACK DECOMPOSE\n"
        "- **Эпик:** T-HUB-022\n"
    )
    mode = handoff_mode_from_text(legacy_text)
    assert mode == "DECOMPOSE"


def test_validate_frontmatter_errors():
    invalid_schema = "---\nschema: unknown/v1\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-HUB\n---\n"
    meta, errors = validate_handoff_frontmatter(invalid_schema)
    assert meta is None
    assert errors == ["handoff_frontmatter_schema_invalid"]

    bad_fields = "---\nschema: loop-handoff/v1\nrole: INVALID\nmode: IMPLEMENT\nepic_id: T-HUB\n---\n"
    meta, errors = validate_handoff_frontmatter(bad_fields)
    assert meta is None
    assert len(errors) > 0
    assert any("role" in err for err in errors)
