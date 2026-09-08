"""Tests for context telemetry aggregation, secret redaction, and finish receipt.

Addresses FR-005, FR-007, FR-008, FR-010.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from harness.hooks.context_ledger import (
    ContextLedger,
    ReadRequest,
    compute_content_hash,
)
from harness.hooks.context_telemetry import (
    build_finish_receipt,
    collect_session_telemetry,
    format_telemetry_summary,
    redact_path,
    verify_telemetry_secret_free,
)
from loop.schemas.telemetry import (
    SCHEMA_CONTEXT_TELEMETRY,
    SCHEMA_FINISH_RECEIPT,
    ActorTelemetry,
    FinishReceipt,
    TelemetryAggregate,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "telemetry_project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_collect_session_telemetry_aggregate_counters(workspace: Path):
    doc_a = workspace / "doc_a.py"
    doc_a.write_text("def a():\n    return 1\n", encoding="utf-8")
    doc_b = workspace / "doc_b.py"
    doc_b.write_text("def b():\n    return 2\n", encoding="utf-8")

    sess_id = "sess-telemetry-1"
    runtime_dir = workspace / ".claude" / "runtime"

    # Root actor (Claude)
    root_ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="root",
        runtime_provider="claude",
        actor_kind="root",
        runtime_dir=runtime_dir,
    )
    # 1. Unique read doc_a
    r1 = root_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 2], "implement"))
    assert r1.decision == "allowed"
    # 2. Duplicate read doc_a
    r2 = root_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 2], "implement"))
    assert r2.decision == "duplicate"
    # 3. Read doc_b
    r3 = root_ledger.decide(ReadRequest(str(doc_b), compute_content_hash(doc_b), [1, 2], "implement"))
    assert r3.decision == "allowed"
    root_ledger.record_search_exception()

    # Subagent actor (Codex)
    sub_ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="subagent-1",
        runtime_provider="codex",
        actor_kind="subagent",
        parent_invocation_id="root",
        runtime_dir=runtime_dir,
    )
    # 4. Unique read doc_a for subagent
    r4 = sub_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 2], "implement"))
    assert r4.decision == "allowed"
    sub_ledger.record_monolith_attempt()

    # Collect session telemetry
    agg, diag = collect_session_telemetry(workspace, sess_id, runtime_dir=runtime_dir)
    assert diag is None
    assert agg is not None
    assert agg.unique_reads == 3  # 2 from root, 1 from subagent
    assert agg.duplicate_reads == 1
    assert agg.search_exceptions == 1
    assert agg.monolith_plan_attempts == 1
    assert agg.files_tracked == 2
    assert agg.highest_repeat_path == "doc_a.py"
    assert agg.is_green is True
    assert len(agg.actors) == 2


def test_actor_attribution_and_provider_breakdown(workspace: Path):
    doc_a = workspace / "module.py"
    doc_a.write_text("x = 10\n", encoding="utf-8")
    sess_id = "sess-attrib-1"
    runtime_dir = workspace / ".claude" / "runtime"

    # Root (claude)
    root_ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="root",
        runtime_provider="claude",
        actor_kind="root",
        runtime_dir=runtime_dir,
    )
    root_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 1], "implement"))

    # Child 1 (claude subagent)
    c1_ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="sub-c1",
        runtime_provider="claude",
        actor_kind="subagent",
        parent_invocation_id="root",
        runtime_dir=runtime_dir,
    )
    c1_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 1], "implement"))

    # Child 2 (codex subagent)
    c2_ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="sub-c2",
        runtime_provider="codex",
        actor_kind="subagent",
        parent_invocation_id="root",
        runtime_dir=runtime_dir,
    )
    c2_ledger.decide(ReadRequest(str(doc_a), compute_content_hash(doc_a), [1, 1], "implement"))
    c2_ledger.record_monolith_attempt()

    agg, diag = collect_session_telemetry(workspace, sess_id, runtime_dir=runtime_dir)
    assert diag is None
    assert agg is not None

    actors_by_id = {a.agent_invocation_id: a for a in agg.actors}
    assert "root" in actors_by_id
    assert actors_by_id["root"].actor_kind == "root"
    assert actors_by_id["root"].runtime_provider == "claude"
    assert actors_by_id["root"].unique_reads == 1

    assert "sub-c1" in actors_by_id
    assert actors_by_id["sub-c1"].actor_kind == "subagent"
    assert actors_by_id["sub-c1"].parent_invocation_id == "root"
    assert actors_by_id["sub-c1"].runtime_provider == "claude"

    assert "sub-c2" in actors_by_id
    assert actors_by_id["sub-c2"].actor_kind == "subagent"
    assert actors_by_id["sub-c2"].runtime_provider == "codex"
    assert actors_by_id["sub-c2"].monolith_plan_attempts == 1

    # Provider breakdown
    assert "claude" in agg.provider_breakdown
    assert "codex" in agg.provider_breakdown
    assert agg.provider_breakdown["claude"]["unique_reads"] == 2
    assert agg.provider_breakdown["codex"]["unique_reads"] == 1
    assert agg.provider_breakdown["codex"]["monolith_plan_attempts"] == 1


def test_build_finish_receipt_green_status(workspace: Path):
    doc = workspace / "foo.py"
    doc.write_text("print(1)\n", encoding="utf-8")
    sess_id = "sess-receipt-green"
    runtime_dir = workspace / ".claude" / "runtime"

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id=sess_id,
        agent_invocation_id="root",
        runtime_provider="claude",
        actor_kind="root",
        runtime_dir=runtime_dir,
    )
    ledger.decide(ReadRequest(str(doc), compute_content_hash(doc), [1, 1], "implement"))

    receipt = build_finish_receipt(workspace, sess_id, epic_id="T-HUB-078", step_id="s04", runtime_dir=runtime_dir)
    assert receipt.schema_version == SCHEMA_FINISH_RECEIPT
    assert receipt.status == "green"
    assert receipt.aggregate.is_green is True
    assert receipt.aggregate.unique_reads == 1
    assert receipt.aggregate.duplicate_reads == 0
    assert receipt.secret_free is True
    assert receipt.diagnostics == []

    summary = format_telemetry_summary(receipt)
    assert "unique_reads=1" in summary
    assert "duplicate_reads=0" in summary
    assert "(green)" in summary


def test_corrupt_or_missing_ledger_failure(workspace: Path):
    sess_id = "sess-corrupt"
    runtime_dir = workspace / ".claude" / "runtime"

    # 1. Missing ledger
    receipt_missing = build_finish_receipt(workspace, "non-existent-session", runtime_dir=runtime_dir)
    assert receipt_missing.status == "missing"
    assert receipt_missing.aggregate.is_green is False
    assert "missing_ledger" in receipt_missing.diagnostics
    summary_missing = format_telemetry_summary(receipt_missing)
    assert "[NON-GREEN: missing_ledger]" in summary_missing

    # 2. Corrupt JSON in ledger
    sess_dir = runtime_dir / "context-ledger" / workspace.name / sess_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    (sess_dir / "root.json").write_text("{ invalid json ", encoding="utf-8")

    agg, diag = collect_session_telemetry(workspace, sess_id, runtime_dir=runtime_dir)
    assert agg is None
    assert diag == "corrupt_ledger"

    receipt_corrupt = build_finish_receipt(workspace, sess_id, runtime_dir=runtime_dir)
    assert receipt_corrupt.status == "corrupt"
    assert receipt_corrupt.aggregate.is_green is False
    assert "corrupt_ledger" in receipt_corrupt.diagnostics
    summary_corrupt = format_telemetry_summary(receipt_corrupt)
    assert "[NON-GREEN: corrupt_ledger]" in summary_corrupt


def test_secret_free_verification_and_path_redaction(workspace: Path):
    clean_data = {
        "schema": "context-ledger/v1",
        "counters": {"unique_reads": 1, "duplicate_reads": 0},
        "files": {"/some/path.py": {"read_count": 1}},
    }
    is_clean, violations = verify_telemetry_secret_free(clean_data)
    assert is_clean is True
    assert violations == []

    # Dirty data with secret keys
    dirty_data = {
        "schema": "context-ledger/v1",
        "file_content": "def secret(): pass",
        "token": "sk-12345",
    }
    is_clean_d, violations_d = verify_telemetry_secret_free(dirty_data)
    assert is_clean_d is False
    assert any("forbidden_key:root.file_content" in v for v in violations_d)
    assert any("forbidden_key:root.token" in v for v in violations_d)

    # Path redaction
    rel_path = workspace / "nested" / "target.py"
    redacted = redact_path(str(rel_path), workspace)
    assert redacted == "nested/target.py"

    outside_path = Path("/etc/shadow")
    redacted_out = redact_path(str(outside_path), workspace)
    assert redacted_out == "shadow"
