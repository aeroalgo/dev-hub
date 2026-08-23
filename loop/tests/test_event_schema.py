from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import (  # noqa: E402
    EVENT_SCHEMA,
    EventDiagnostic,
    build_event,
    event_revision_key,
    normalize_artifact_path,
    validate_event,
)


def _load_epic_lib():
    path = ROOT / ".claude" / "hooks" / "epic_lib.py"
    spec = importlib.util.spec_from_file_location("epic_lib_event_schema", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_valid_v2_event_round_trips_with_required_types() -> None:
    event = build_event(
        epic_id="T-035-loop-state-prod-hardening",
        kind="qa_pass",
        artifact="memory-bank/back/qa/demo.yaml",
        artifact_sha256="a" * 64,
        seq=3,
        epoch=2,
        timestamp="2026-08-05T12:00:00+00:00",
        metadata={"runner": "loop", "attempt": 1},
    )

    result = validate_event(event, expected_epic_id=event["epic_id"])

    assert result.valid
    assert result.event == event
    assert result.event["schema"] == EVENT_SCHEMA


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("seq", 0, "seq"),
        ("kind", "unknown", "kind"),
        ("artifact_sha256", "not-a-hash", "artifact_hash"),
        ("artifact", "../secret.txt", "artifact_path"),
        ("epoch", -1, "epoch"),
        ("metadata", {"api_token": "hidden"}, "metadata_secret"),
    ],
)
def test_invalid_required_fields_types_and_paths_return_diagnostics(
    field: str, value: object, code: str
) -> None:
    event = build_event(
        epic_id="demo",
        kind="qa_pass",
        artifact="memory-bank/back/qa/demo.yaml",
        artifact_sha256="a" * 64,
        seq=1,
        timestamp="2026-08-05T12:00:00+00:00",
    )
    event[field] = value

    result = validate_event(event, expected_epic_id="demo")

    assert not result.valid
    assert any(isinstance(item, EventDiagnostic) and item.code == code for item in result.diagnostics)


def test_revision_key_separates_changed_content_and_kind() -> None:
    base = build_event(
        epic_id="demo",
        kind="qa_pass",
        artifact="memory-bank/back/qa/demo.yaml",
        artifact_sha256="a" * 64,
        seq=1,
        timestamp="2026-08-05T12:00:00+00:00",
    )
    same = dict(base)
    changed_hash = dict(base, artifact_sha256="b" * 64)
    changed_kind = dict(base, kind="qa_fail")

    assert event_revision_key(base) == event_revision_key(same)
    assert event_revision_key(base) != event_revision_key(changed_hash)
    assert event_revision_key(base) != event_revision_key(changed_kind)


def test_append_event_uses_content_hash_for_revision_dedupe(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    artifact = tmp_path / "memory-bank/back/qa/demo.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("verdict: pass\n", encoding="utf-8")

    assert lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)
    assert not lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)
    artifact.write_text("verdict: fail\n", encoding="utf-8")
    assert lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)

    event_path = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    assert len(event_path.read_text(encoding="utf-8").splitlines()) == 2


def test_metadata_rejects_unbounded_payload() -> None:
    event = build_event(
        epic_id="demo",
        kind="qa_pass",
        artifact="memory-bank/back/qa/demo.yaml",
        artifact_sha256=hashlib.sha256(b"x").hexdigest(),
        seq=1,
        timestamp="2026-08-05T12:00:00+00:00",
    )
    event["metadata"] = {"details": "x" * 300}

    result = validate_event(event, expected_epic_id="demo")

    assert not result.valid
    assert any(item.code == "metadata_value" for item in result.diagnostics)


def test_artifact_paths_are_normalized_to_repo_relative_posix() -> None:
    assert normalize_artifact_path("memory-bank\\back\\qa\\demo.yaml")[0] == "memory-bank/back/qa/demo.yaml"
    assert normalize_artifact_path("/tmp/demo.yaml")[0] is None
