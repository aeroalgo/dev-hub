"""Tests for loop.schemas.event."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from epic_events import build_event
from loop.schemas.event import EVENT_KINDS, EVENT_SCHEMA, LoopEvent


def test_loop_event_valid() -> None:
    event = LoopEvent(
        event_id="a" * 32,
        seq=1,
        kind="qa_pass",
        artifact="memory-bank/back/qa.md",
        artifact_sha256="b" * 64,
        epic_id="T-HUB-022",
        epoch=0,
        t="2026-08-31T00:00:00Z",
        metadata={"key": "val"},
    )
    assert event.schema_version == EVENT_SCHEMA
    dump = event.model_dump(by_alias=True)
    assert dump["schema"] == "loop-event/v2"
    assert dump["event_id"] == "a" * 32


def test_loop_event_missing_type() -> None:
    with pytest.raises(ValidationError):
        LoopEvent(
            event_id="a" * 32,
            seq=1,
            # missing kind
            artifact="memory-bank/back/qa.md",
            artifact_sha256="b" * 64,
            epic_id="T-HUB-022",
            t="2026-08-31T00:00:00Z",
        )  # type: ignore[call-arg]


def test_loop_event_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        LoopEvent(
            event_id="a" * 32,
            seq=1,
            kind="invalid_kind",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="b" * 64,
            epic_id="T-HUB-022",
            t="2026-08-31T00:00:00Z",
        )


def test_loop_event_invalid_seq() -> None:
    with pytest.raises(ValidationError):
        LoopEvent(
            event_id="a" * 32,
            seq=0,
            kind="qa_pass",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="b" * 64,
            epic_id="T-HUB-022",
            t="2026-08-31T00:00:00Z",
        )


def test_loop_event_invalid_sha256() -> None:
    with pytest.raises(ValidationError):
        LoopEvent(
            event_id="a" * 32,
            seq=1,
            kind="qa_pass",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="not_sha256",
            epic_id="T-HUB-022",
            t="2026-08-31T00:00:00Z",
        )


def test_loop_event_round_trip() -> None:
    dict_event = build_event(
        epic_id="T-HUB-022",
        kind="qa_pass",
        artifact="memory-bank/back/qa.md",
        artifact_sha256="c" * 64,
        seq=1,
        timestamp="2026-08-31T12:00:00Z",
    )
    validated = LoopEvent.model_validate(dict_event)
    assert validated.epic_id == "T-HUB-022"
    assert validated.schema_version == EVENT_SCHEMA
    assert validated.artifact == "memory-bank/back/qa.md"


def test_append_event_invalid_raises() -> None:
    with pytest.raises(ValueError):
        build_event(
            epic_id="T-HUB-022",
            kind="invalid_kind_foo",
            artifact="memory-bank/back/qa.md",
            artifact_sha256="c" * 64,
            seq=1,
            timestamp="2026-08-31T12:00:00Z",
        )
