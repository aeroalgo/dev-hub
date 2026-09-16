"""Tests for canonical loop-event schemas via epic_events."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import (  # noqa: E402
    EVENT_KINDS,
    EVENT_SCHEMA,
    build_event,
    validate_event,
)


def test_canonical_event_valid() -> None:
    event = build_event(
        epic_id="T-HUB-022",
        kind="qa_pass",
        artifact="memory-bank/back/qa.md",
        artifact_sha256="b" * 64,
        seq=1,
        epoch=0,
        timestamp="2026-08-31T00:00:00Z",
        metadata={"key": "val"},
    )
    assert event["schema"] == EVENT_SCHEMA
    assert event["schema"] == "loop-event/v2"
    assert event["epic_id"] == "T-HUB-022"
    result = validate_event(event, expected_epic_id="T-HUB-022")
    assert result.valid is True


def test_canonical_event_invalid_kind() -> None:
    with pytest.raises(ValueError, match="kind must be one of"):
        build_event(
            epic_id="T-HUB-022",
            kind="invalid_kind",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="b" * 64,
            seq=1,
            timestamp="2026-08-31T00:00:00Z",
        )


def test_canonical_event_invalid_seq() -> None:
    with pytest.raises(ValueError, match="seq must be a positive integer"):
        build_event(
            epic_id="T-HUB-022",
            kind="qa_pass",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="b" * 64,
            seq=0,
            timestamp="2026-08-31T00:00:00Z",
        )


def test_canonical_event_invalid_sha256() -> None:
    event = build_event(
        epic_id="T-HUB-022",
        kind="qa_pass",
        artifact="memory-bank/back/qa.md",
        artifact_sha256="b" * 64,
        seq=1,
        timestamp="2026-08-31T00:00:00Z",
    )
    event["artifact_sha256"] = "not_sha256"
    result = validate_event(event, expected_epic_id="T-HUB-022")
    assert result.valid is False
    assert any(d.code == "artifact_hash" for d in result.diagnostics)


def test_canonical_event_round_trip() -> None:
    dict_event = build_event(
        epic_id="T-HUB-022",
        kind="qa_pass",
        artifact="memory-bank/back/qa.md",
        artifact_sha256="c" * 64,
        seq=1,
        timestamp="2026-08-31T12:00:00Z",
    )
    validation = validate_event(dict_event, expected_epic_id="T-HUB-022")
    assert validation.valid is True
    assert validation.event is not None
    assert validation.event["epic_id"] == "T-HUB-022"
    assert validation.event["schema"] == EVENT_SCHEMA
    assert validation.event["artifact"] == "memory-bank/back/qa.md"


def test_build_event_rejects_reflection_done() -> None:
    with pytest.raises(ValueError, match="kind must be one of"):
        build_event(
            epic_id="demo",
            kind="reflection_done",
            artifact="memory-bank/back/reflection/reflection-demo.md",
            artifact_sha256="c" * 64,
            seq=1,
            timestamp="2026-08-31T12:00:00Z",
        )
    assert "reflection_done" not in EVENT_KINDS
