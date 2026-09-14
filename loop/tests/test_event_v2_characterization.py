from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import (  # noqa: E402
    EVENT_KINDS,
    EVENT_LOG_SIDECAR_SCHEMAS,
    EVENT_SCHEMA,
    LEGACY_DEAD_EVENT_KINDS,
    adapt_v1_event,
    build_event,
    event_stream_digest,
    migrate_event_log,
    read_event_log_result,
    validate_event,
)


def _sample_v2_event(epic_id: str = "T-HUB-089", seq: int = 1, kind: str = "qa_pass") -> dict[str, object]:
    artifact = f"memory-bank/back/qa/{epic_id}-step-{seq}.yaml"
    return build_event(
        epic_id=epic_id,
        kind=kind,
        artifact=artifact,
        artifact_sha256=hashlib.sha256(artifact.encode()).hexdigest(),
        seq=seq,
        timestamp=f"2026-09-12T10:00:{seq:02d}+00:00",
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records),
        encoding="utf-8",
    )


def test_v2_event_canonical_schema_and_validation() -> None:
    """Characterize canonical loop-event/v2 record validation and structure."""
    event = _sample_v2_event("T-HUB-089", 1, "implement_done")

    assert event["schema"] == EVENT_SCHEMA
    assert event["schema"] == "loop-event/v2"
    assert event["epic_id"] == "T-HUB-089"
    assert event["seq"] == 1
    assert event["kind"] == "implement_done"
    assert len(str(event["artifact_sha256"])) == 64

    validation = validate_event(event, expected_epic_id="T-HUB-089")
    assert validation.valid is True
    assert validation.diagnostics == ()
    assert validation.event == event


def test_v2_event_all_canonical_kinds_validate_cleanly() -> None:
    """Characterize that all 17 canonical event kinds validate under loop-event/v2."""
    assert len(EVENT_KINDS) == 17
    for seq, kind in enumerate(sorted(EVENT_KINDS), start=1):
        event = _sample_v2_event("T-HUB-089", seq, kind)
        validation = validate_event(event, expected_epic_id="T-HUB-089")
        assert validation.valid is True
        assert validation.event is not None
        assert validation.event["kind"] == kind


def test_v2_event_validation_denial_on_invalid_fields() -> None:
    """Characterize validation failures on malformed fields or mismatched epic."""
    valid = _sample_v2_event("T-HUB-089", 1, "qa_pass")

    # Wrong schema
    bad_schema = dict(valid, schema="loop-event/v1")
    val_schema = validate_event(bad_schema, expected_epic_id="T-HUB-089")
    assert val_schema.valid is False
    assert any(d.code == "schema" for d in val_schema.diagnostics)

    # Missing required field
    missing_kind = {k: v for k, v in valid.items() if k != "kind"}
    val_missing = validate_event(missing_kind, expected_epic_id="T-HUB-089")
    assert val_missing.valid is False
    assert any(d.code == "missing_field" and d.field == "kind" for d in val_missing.diagnostics)

    # Invalid sequence (seq < 1)
    bad_seq = dict(valid, seq=0)
    val_seq = validate_event(bad_seq, expected_epic_id="T-HUB-089")
    assert val_seq.valid is False
    assert any(d.code == "seq" for d in val_seq.diagnostics)

    # Invalid sha256 (not 64 hex characters)
    bad_hash = dict(valid, artifact_sha256="invalid-hash")
    val_hash = validate_event(bad_hash, expected_epic_id="T-HUB-089")
    assert val_hash.valid is False
    assert any(d.code == "artifact_hash" for d in val_hash.diagnostics)

    # Mismatched epic
    val_epic = validate_event(valid, expected_epic_id="OTHER-EPIC")
    assert val_epic.valid is False
    assert any(d.code == "epic_ownership" for d in val_epic.diagnostics)

    # Unsafe relative artifact path
    bad_path = dict(valid, artifact="../secret/file.txt")
    val_path = validate_event(bad_path, expected_epic_id="T-HUB-089")
    assert val_path.valid is False
    assert any(d.code == "artifact_path" for d in val_path.diagnostics)

    # Absolute artifact path
    bad_abs = dict(valid, artifact="/etc/passwd")
    val_abs = validate_event(bad_abs, expected_epic_id="T-HUB-089")
    assert val_abs.valid is False
    assert any(d.code == "artifact_absolute" for d in val_abs.diagnostics)

    # Forbidden secret in metadata
    bad_meta = dict(valid, metadata={"api_key": "secret-value"})
    val_meta = validate_event(bad_meta, expected_epic_id="T-HUB-089")
    assert val_meta.valid is False
    assert any(d.code == "metadata_secret" for d in val_meta.diagnostics)


def test_v2_event_stream_replay_across_archive_and_live(tmp_path: Path) -> None:
    """Characterize reading ordered v2 stream across archive and live files."""
    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    archive1 = tmp_path / "memory-bank/back/events/T-HUB-089/archive-01.jsonl"
    archive2 = tmp_path / "memory-bank/back/events/T-HUB-089/archive-02.jsonl"

    e1 = _sample_v2_event("T-HUB-089", 1, "phase_transition")
    e2 = _sample_v2_event("T-HUB-089", 2, "decompose_step_done")
    e3 = _sample_v2_event("T-HUB-089", 3, "implement_done")
    e4 = _sample_v2_event("T-HUB-089", 4, "qa_pass")

    _write_jsonl(archive1, [e1, e2])
    _write_jsonl(archive2, [e3])
    _write_jsonl(event_path, [e4])

    result = read_event_log_result(event_path, expected_epic_id="T-HUB-089", cwd=tmp_path)

    assert result.valid is True
    assert result.archive_count == 2
    assert result.invalid_count == 0
    assert [e["seq"] for e in result.events] == [1, 2, 3, 4]
    assert [e["kind"] for e in result.events] == [
        "phase_transition",
        "decompose_step_done",
        "implement_done",
        "qa_pass",
    ]


def test_archived_dead_event_reflection_done_is_validatable_and_harmless(tmp_path: Path) -> None:
    """Characterize historical reflection_done remaining validatable without breaking replay."""
    assert "reflection_done" in LEGACY_DEAD_EVENT_KINDS
    assert "reflection_done" not in EVENT_KINDS

    dead_event = {
        "schema": EVENT_SCHEMA,
        "event_id": "0123456789abcdef0123456789abcdef",
        "seq": 1,
        "kind": "reflection_done",
        "artifact": "memory-bank/back/qa/T-HUB-089-step-1.yaml",
        "artifact_sha256": hashlib.sha256(b"artifact").hexdigest(),
        "epic_id": "T-HUB-089",
        "epoch": 0,
        "t": "2026-09-12T10:00:01+00:00",
        "metadata": {},
    }
    validation = validate_event(dead_event, expected_epic_id="T-HUB-089")
    assert validation.valid is True

    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    e2 = _sample_v2_event("T-HUB-089", 2, "qa_pass")
    _write_jsonl(event_path, [dead_event, e2])

    result = read_event_log_result(event_path, expected_epic_id="T-HUB-089", cwd=tmp_path)
    assert result.valid is True
    assert [e["seq"] for e in result.events] == [1, 2]
    assert [e["kind"] for e in result.events] == ["reflection_done", "qa_pass"]


def test_characterize_malformed_records_diagnostic_in_log_reader(tmp_path: Path) -> None:
    """Characterize error diagnostics when malformed or corrupted JSON appears."""
    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(
        json.dumps({"schema": "loop-event/v2", "seq": "not-an-int"}) + "\n"
        + "{malformed-json\n",
        encoding="utf-8",
    )

    result = read_event_log_result(event_path, expected_epic_id="T-HUB-089", cwd=tmp_path)
    assert result.valid is False
    assert result.invalid_count == 2
    codes = {d.code for d in result.diagnostics}
    assert "invalid_json" in codes


def test_gate_sidecar_schemas_are_filtered_without_invalidating_stream(tmp_path: Path) -> None:
    """Characterize gate sidecars ignored by read_event_log_result without polluting events."""
    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    v2_event = _sample_v2_event("T-HUB-089", 1, "qa_pass")

    evidence = {
        "schema": "loop-gate-evidence/v1",
        "phase": "QA",
        "epic_id": "T-HUB-089",
        "step_id": "QA",
        "verdict": "PASS",
        "agent_id": "verify-qa",
        "recorded_at": "2026-09-12T10:01:00+00:00",
    }
    verdict = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-qa",
        "session_id": "session-1",
        "epic_id": "T-HUB-089",
        "step_id": "QA",
        "phase": "QA",
        "verdict": "PASS",
        "recorded_at": "2026-09-12T10:01:00+00:00",
    }

    _write_jsonl(event_path, [v2_event, evidence, verdict])

    result = read_event_log_result(event_path, expected_epic_id="T-HUB-089", cwd=tmp_path)
    assert result.valid is True
    assert result.invalid_count == 0
    assert len(result.events) == 1
    assert result.events[0]["kind"] == "qa_pass"


def test_offline_migration_boundary_converts_v1_and_records_digest(tmp_path: Path) -> None:
    """Characterize offline migration tool (migrate_event_log) behavior."""
    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    v1_raw = [
        {"kind": "qa_pass", "artifact": "memory-bank/back/qa/demo-1.yaml", "t": "2026-09-12T10:00:00+00:00"},
        {"kind": "bugfix_done", "artifact": "memory-bank/back/bugfix/demo-2.md", "t": "2026-09-12T11:00:00+00:00"},
    ]
    _write_jsonl(event_path, v1_raw)

    migration_res = migrate_event_log(event_path, epic_id="T-HUB-089", cwd=tmp_path)
    assert migration_res["ok"] is True
    assert migration_res["migrated"] == 2
    assert len(migration_res["events"]) == 2
    assert all(e["schema"] == EVENT_SCHEMA for e in migration_res["events"])
    assert all(e["metadata"]["migrated_from"] == "loop-event/v1" for e in migration_res["events"])

    # Verify idempotency
    second_run = migrate_event_log(event_path, epic_id="T-HUB-089", cwd=tmp_path)
    assert second_run["ok"] is True
    assert second_run["migrated"] == 0
    assert second_run["replay_digest"] == migration_res["replay_digest"]


def test_read_event_log_result_never_calls_adapt_v1_event(tmp_path: Path, monkeypatch) -> None:
    """Control assertion: live read_event_log_result never invokes adapt_v1_event."""
    import epic_events

    def _unexpected_adapt(*args, **kwargs):
        raise AssertionError("adapt_v1_event should not be called in live event reader path")

    monkeypatch.setattr(epic_events, "adapt_v1_event", _unexpected_adapt)

    event_path = tmp_path / "memory-bank/back/events/T-HUB-089/events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)
    v1_raw = [
        {"kind": "qa_pass", "artifact": "memory-bank/back/qa/demo-1.yaml", "t": "2026-09-12T10:00:00+00:00"},
    ]
    _write_jsonl(event_path, v1_raw)

    result = read_event_log_result(event_path, expected_epic_id="T-HUB-089", cwd=tmp_path)
    assert result.valid is False
    assert result.invalid_count == 1
