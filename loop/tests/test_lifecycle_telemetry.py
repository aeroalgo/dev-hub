"""Unit tests for telemetry companion schema, aggregate counters, and legacy marker migration."""

from __future__ import annotations

import json
from pathlib import Path
import time
import pytest

from loop.lifecycle import (
    LEGACY_UNKNOWN,
    InvocationKey,
    InvocationRecord,
    InvocationState,
    LegacyMarkerMigrationError,
    LegacyMarkerResult,
    LifecycleReducer,
    migrate_legacy_marker,
    migrate_legacy_marker_files,
)
from loop.telemetry import (
    SCHEMA_TELEMETRY_COMPANION,
    SessionTelemetryCompanion,
    TelemetryAggregator,
    append_companion_record,
    read_companion_records,
    write_companion_records,
)


def test_companion_jsonl_schema(tmp_path: Path) -> None:
    """cp1: Companion JSONL preserves invocation_id, first_action_at, terminal_reason, retry_chain_id, timestamps."""
    reducer = LifecycleReducer()
    key_root = InvocationKey(session="sess-root-1", phase="back", step="s05", role="orchestrator", epoch=0)
    rec_root = reducer.launch(key_root, owner="orchestrator", lease_duration_sec=30.0)

    # 1. Active root session with first action
    rec_action = reducer.record_first_action(key_root, actor="orchestrator", timestamp=100.5)

    comp_active = SessionTelemetryCompanion.from_invocation_record(
        rec_action,
        is_root=True,
        retry_chain_id="chain-abc-123",
        tool_actions_count=3,
    )

    assert comp_active.invocation_id == rec_action.invocation_id
    assert comp_active.session_id == "sess-root-1"
    assert comp_active.role == "orchestrator"
    assert comp_active.step == "s05"
    assert comp_active.phase == "back"
    assert comp_active.is_root is True
    assert comp_active.first_action_taken is True
    assert comp_active.first_action_at == 100.5
    assert comp_active.retry_chain_id == "chain-abc-123"
    assert comp_active.retry_count == 0
    assert comp_active.tool_actions_count == 3
    assert comp_active.schema_version == SCHEMA_TELEMETRY_COMPANION
    assert comp_active.retry_relation == {
        "retry_chain_id": "chain-abc-123",
        "retry_count": 0,
        "epoch": 0,
        "is_retry": True,
    }
    assert comp_active.to_dict()["retry_relation"] == comp_active.retry_relation

    # Verify timestamps dictionary structure
    ts = comp_active.timestamps
    assert "created_at" in ts
    assert "updated_at" in ts
    assert "first_action_at" in ts
    assert ts["first_action_at"] == 100.5
    assert "closed_at" in ts
    assert "lease_expires_at" in ts

    # 2. Terminal session with aborted_before_action (empty root session with cause)
    key_empty = InvocationKey(session="sess-empty-1", phase="back", step="s05", role="orchestrator", epoch=0)
    reducer.launch(key_empty, owner="orchestrator")
    rec_aborted = reducer.abort_before_action(
        key_empty,
        actor="orchestrator",
        reason="prompt validation failed before start: empty prompt payload",
    )

    comp_aborted = SessionTelemetryCompanion.from_invocation_record(
        rec_aborted,
        is_root=True,
        retry_chain_id="chain-empty-999",
        tool_actions_count=0,
        closed_at=rec_aborted.updated_at,
    )

    assert comp_aborted.is_root is True
    assert comp_aborted.state == InvocationState.ABORTED_BEFORE_ACTION.value
    assert comp_aborted.terminal_state == InvocationState.ABORTED_BEFORE_ACTION.value
    assert comp_aborted.terminal_reason == "prompt validation failed before start: empty prompt payload"
    assert comp_aborted.first_action_taken is False
    assert comp_aborted.first_action_at is None
    assert comp_aborted.is_zero_action is True
    assert comp_aborted.is_terminal is True
    assert comp_aborted.duration_sec is not None

    # 3. Subagent session serialization and deserialization
    comp_subagent = SessionTelemetryCompanion(
        invocation_id="inv-sub-456",
        session_id="sess-sub-456",
        invocation_key="sess-sub-456:back:s05:worker:0",
        role="worker",
        step="s05",
        phase="back",
        owner="worker:pool-1",
        state=InvocationState.PASSED.value,
        is_root=False,
        terminal_state=InvocationState.PASSED.value,
        terminal_reason="verification passed",
        first_action_taken=True,
        first_action_at=120.0,
        retry_chain_id="chain-abc-123",
        retry_count=0,
        epoch=0,
        tool_actions_count=5,
        created_at=100.0,
        updated_at=130.0,
        closed_at=130.0,
        duration_sec=30.0,
    )

    assert comp_subagent.is_root is False
    assert comp_subagent.is_zero_action is False

    restored = comp_subagent.to_dict()
    restored["retry_chain_id"] = None
    restored["retry_count"] = 0
    restored["epoch"] = 0
    restored["retry_relation"] = {
        "retry_chain_id": "chain-retry-789",
        "retry_count": 3,
        "epoch": 4,
        "is_retry": True,
    }
    restored_companion = SessionTelemetryCompanion.from_dict(restored)
    assert restored_companion.retry_chain_id == "chain-retry-789"
    assert restored_companion.retry_count == 3
    assert restored_companion.epoch == 4

    # 4. JSONL file persistence and roundtrip
    jsonl_path = tmp_path / "companion_telemetry.jsonl"
    write_companion_records(jsonl_path, [comp_active, comp_aborted])
    append_companion_record(jsonl_path, comp_subagent)

    loaded = read_companion_records(jsonl_path)
    assert len(loaded) == 3
    assert loaded[0].invocation_id == comp_active.invocation_id
    assert loaded[0].first_action_at == 100.5
    assert loaded[1].invocation_id == comp_aborted.invocation_id
    assert loaded[1].terminal_reason == "prompt validation failed before start: empty prompt payload"
    assert loaded[1].first_action_at is None
    assert loaded[2].invocation_id == "inv-sub-456"
    assert loaded[2].is_root is False

    # Verify JSON line validity
    with jsonl_path.open("r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert "invocation_id" in parsed
        assert "timestamps" in parsed
        assert "schema_version" in parsed or "schema" in parsed

    # 5. Enforce zero-action consistency and reject invalid states
    with pytest.raises(ValueError, match="first_action_at must be None"):
        SessionTelemetryCompanion(
            invocation_id="inv-bad-1",
            session_id="sess-bad",
            invocation_key="sess-bad:back:s05:w:0",
            role="worker",
            step="s05",
            phase="back",
            owner="worker",
            state=InvocationState.ABORTED_BEFORE_ACTION.value,
            first_action_taken=False,
            first_action_at=100.0,
            tool_actions_count=0,
        )

    with pytest.raises(ValueError, match="tool_actions_count must be 0"):
        SessionTelemetryCompanion(
            invocation_id="inv-bad-2",
            session_id="sess-bad",
            invocation_key="sess-bad:back:s05:w:0",
            role="worker",
            step="s05",
            phase="back",
            owner="worker",
            state=InvocationState.ABORTED_BEFORE_ACTION.value,
            first_action_taken=False,
            first_action_at=None,
            tool_actions_count=2,
        )


def test_aggregate_counters(tmp_path: Path) -> None:
    """cp2: Aggregate counters correctly calculate duplicate-suppressed, terminal causes, zero-action sessions."""
    aggregator = TelemetryAggregator()

    # 1. Create companion records representing different scenarios
    # Session 1: Passed root session with actions
    s1 = SessionTelemetryCompanion(
        invocation_id="inv-1",
        session_id="sess-1",
        invocation_key="sess-1:back:s05:orch:0",
        role="orch",
        step="s05",
        phase="back",
        owner="orch",
        state=InvocationState.PASSED.value,
        is_root=True,
        terminal_state=InvocationState.PASSED.value,
        terminal_reason="gate_passed",
        first_action_taken=True,
        first_action_at=10.0,
        retry_chain_id="chain-1",
        tool_actions_count=4,
    )

    # Session 2: Aborted root session before action (zero-action)
    s2 = SessionTelemetryCompanion(
        invocation_id="inv-2",
        session_id="sess-2",
        invocation_key="sess-2:back:s05:orch:0",
        role="orch",
        step="s05",
        phase="back",
        owner="orch",
        state=InvocationState.ABORTED_BEFORE_ACTION.value,
        is_root=True,
        terminal_state=InvocationState.ABORTED_BEFORE_ACTION.value,
        terminal_reason="aborted_before_action:syntax_error",
        first_action_taken=False,
        first_action_at=None,
        retry_chain_id="chain-2",
        tool_actions_count=0,
    )

    # Session 3: Subagent cancelled via TaskStop
    s3 = SessionTelemetryCompanion(
        invocation_id="inv-3",
        session_id="sess-3",
        invocation_key="sess-3:back:s05:worker:0",
        role="worker",
        step="s05",
        phase="back",
        owner="worker",
        state=InvocationState.CANCELLED.value,
        is_root=False,
        terminal_state=InvocationState.CANCELLED.value,
        terminal_reason="task_stop:user_interrupt",
        first_action_taken=True,
        first_action_at=15.0,
        retry_chain_id="chain-1",
        tool_actions_count=2,
    )

    # Session 4: Stale session (zero-action)
    s4 = SessionTelemetryCompanion(
        invocation_id="inv-4",
        session_id="sess-4",
        invocation_key="sess-4:back:s05:worker:0",
        role="worker",
        step="s05",
        phase="back",
        owner="worker",
        state=InvocationState.STALE.value,
        is_root=False,
        terminal_state=InvocationState.STALE.value,
        terminal_reason="lease_expired",
        first_action_taken=False,
        first_action_at=None,
        retry_chain_id="chain-3",
        tool_actions_count=0,
    )

    # 2. Record sessions in aggregator
    aggregator.record_session(s1)
    aggregator.record_session(s2)
    aggregator.record_session(s3)
    aggregator.record_session(s4)

    # Record duplicate suppression events
    aggregator.record_duplicate_suppressed("sess-1:back:s05:orch:0", count=3)
    aggregator.record_duplicate_suppressed("sess-3:back:s05:worker:0", count=2)

    # Record legacy marker
    aggregator.record_legacy_marker()

    summary = aggregator.to_dict()

    # 3. Assert counts and distributions
    assert summary["total_sessions"] == 4
    assert summary["root_sessions"] == 2
    assert summary["subagent_sessions"] == 2
    assert summary["duplicate_suppressed"] == 5
    assert summary["duplicate-suppressed"] == 5
    assert summary["zero_action_sessions"] == 2
    assert summary["zero-action-sessions"] == 2
    assert summary["legacy_unknown_count"] == 1

    # Check terminal causes distribution
    causes = summary["terminal_by_cause"]
    assert causes["gate_passed"] == 1
    assert causes["aborted_before_action:syntax_error"] == 1
    assert causes["task_stop:user_interrupt"] == 1
    assert causes["lease_expired"] == 1
    assert causes[LEGACY_UNKNOWN] == 1

    # Check retry chains
    chains = summary["retry_chains"]
    assert "chain-1" in chains
    assert chains["chain-1"] == ["inv-1", "inv-3"]
    assert "chain-2" in chains
    assert chains["chain-2"] == ["inv-2"]

    # 4. Test loading and aggregating directly from JSONL file
    jsonl_file = tmp_path / "sessions.jsonl"
    write_companion_records(jsonl_file, [s1, s2, s3, s4])
    file_agg = TelemetryAggregator.from_jsonl(jsonl_file)
    assert file_agg.total_sessions == 4
    assert file_agg.zero_action_sessions == 2
    assert file_agg.root_sessions == 2
    assert file_agg.subagent_sessions == 2


def test_legacy_marker_migration_unknown(tmp_path: Path) -> None:
    """cp3: Legacy marker migration marks records as legacy_unknown and strictly prevents conversion to PASSED."""
    # 1. Create legacy marker files with old formats that claim passed / success
    marker_dir = tmp_path / "legacy_markers"
    marker_dir.mkdir()

    # File 1: JSON file claiming "passed"
    m1 = marker_dir / "step_s01.marker"
    m1.write_text(json.dumps({
        "status": "passed",
        "gate": "verify-implement",
        "session": "sess-old-1",
        "step": "s01",
        "timestamp": 1234567.0,
    }), encoding="utf-8")

    # File 2: Text file with raw "PASSED"
    m2 = marker_dir / "gate.pass"
    m2.write_text("PASSED\nverdict=true\n", encoding="utf-8")

    # File 3: JSON file with verdict "success"
    m3 = marker_dir / "legacy_result.json"
    m3.write_text(json.dumps({
        "verdict": "SUCCESS",
        "result": "ok",
        "invocation_id": "inv-old-99",
    }), encoding="utf-8")

    # 2. Migrate individual markers
    res1 = migrate_legacy_marker(m1)
    assert res1.diagnostic_status == LEGACY_UNKNOWN
    assert res1.is_passed is False
    assert res1.migrated_state != InvocationState.PASSED
    assert res1.migrated_state == InvocationState.FAILED
    assert "legacy_unknown" in res1.reason

    res2 = migrate_legacy_marker(m2)
    assert res2.diagnostic_status == LEGACY_UNKNOWN
    assert res2.is_passed is False
    assert res2.migrated_state == InvocationState.FAILED

    res3 = migrate_legacy_marker(m3)
    assert res3.diagnostic_status == LEGACY_UNKNOWN
    assert res3.is_passed is False
    assert res3.invocation_id == "inv-old-99"

    # In-memory dict migration
    res_dict = migrate_legacy_marker({"status": "passed", "session": "sess-memory"})
    assert res_dict.diagnostic_status == LEGACY_UNKNOWN
    assert res_dict.is_passed is False
    assert res_dict.migrated_state == InvocationState.FAILED

    # 3. Strictly forbid converting legacy marker result to PASSED
    with pytest.raises(LegacyMarkerMigrationError):
        LegacyMarkerResult(
            source="test",
            diagnostic_status=LEGACY_UNKNOWN,
            migrated_state=InvocationState.PASSED,
            is_passed=False,
        )

    with pytest.raises(LegacyMarkerMigrationError):
        LegacyMarkerResult(
            source="test",
            diagnostic_status=LEGACY_UNKNOWN,
            migrated_state=InvocationState.FAILED,
            is_passed=True,
        )

    # 4. Test directory batch migration
    batch_results = migrate_legacy_marker_files(marker_dir)
    assert len(batch_results) == 3
    for b_res in batch_results:
        assert b_res.diagnostic_status == LEGACY_UNKNOWN
        assert b_res.is_passed is False
        assert b_res.migrated_state != InvocationState.PASSED

    # 5. Ingest into LifecycleReducer
    reducer = LifecycleReducer()
    rec, mig_res = reducer.ingest_legacy_marker(m1, actor="orchestrator:migrator")

    assert rec.state == InvocationState.FAILED
    assert rec.is_terminal is True
    assert rec.key.session == "sess-old-1"
    assert rec.key.step == "s01"
    assert mig_res.diagnostic_status == LEGACY_UNKNOWN
    assert mig_res.is_passed is False

    # Verify reducer forbids transitioning ingested legacy marker to PASSED
    with pytest.raises(Exception):
        reducer.pass_invocation(rec.key, actor="orchestrator:migrator")
