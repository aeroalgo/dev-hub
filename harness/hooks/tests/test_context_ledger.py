"""Tests for ContextLedger, interval algebra, actor isolation, and persistence.
Addresses FR-001, FR-008, FR-009, FR-010.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

from context_ledger import (
    ActorKey,
    ContextLedger,
    DecisionReceipt,
    ReadRecord,
    ReadRequest,
    _LedgerFileLock,
    canonicalize_path,
    compute_content_hash,
    interval_subtract,
    interval_union,
    normalize_intervals,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_duplicate_full_read_returns_cached_or_denied_receipt(workspace: Path):
    target_file = workspace / "sample.py"
    target_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-1",
        agent_invocation_id="root-inv",
        runtime_provider="claude",
        actor_kind="root",
    )

    req1 = ReadRequest(
        raw_path=target_file,
        project_root=workspace,
        root_session_id="session-1",
        agent_invocation_id="root-inv",
        line_interval=(1, 5),
    )
    receipt1 = ledger.decide(req1)
    assert receipt1.decision == "allowed"
    assert receipt1.cached is False
    assert receipt1.reason_code in ("uncached_interval", "new_read")
    assert receipt1.allowed_intervals == [[1, 5]]
    assert receipt1.cached_intervals == []

    # Second identical read
    req2 = ReadRequest(
        raw_path=target_file,
        project_root=workspace,
        root_session_id="session-1",
        agent_invocation_id="root-inv",
        line_interval=(1, 5),
    )
    receipt2 = ledger.decide(req2)
    assert receipt2.decision == "duplicate"
    assert receipt2.cached is True
    assert receipt2.reason_code == "duplicate_range"
    assert receipt2.allowed_intervals == []
    assert receipt2.cached_intervals == [[1, 5]]

    telem = ledger.get_telemetry()
    assert telem["duplicate_reads"] == 1
    assert telem["unique_reads"] == 1


def test_canonical_path_alias_deduplication(workspace: Path):
    target_file = workspace / "module.py"
    target_file.write_text("def func():\n    pass\n", encoding="utf-8")
    symlink_file = workspace / "module_symlink.py"
    try:
        symlink_file.symlink_to(target_file)
    except OSError:
        pass

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-alias",
        agent_invocation_id="root-inv",
    )

    # 1. Read via relative path
    rel_req = ReadRequest(
        raw_path="module.py",
        project_root=workspace,
        root_session_id="session-alias",
        agent_invocation_id="root-inv",
        line_interval=(1, 2),
    )
    r1 = ledger.decide(rel_req)
    assert r1.decision == "allowed"

    # 2. Read via ./module.py
    dot_req = ReadRequest(
        raw_path="./module.py",
        project_root=workspace,
        root_session_id="session-alias",
        agent_invocation_id="root-inv",
        line_interval=(1, 2),
    )
    r2 = ledger.decide(dot_req)
    assert r2.decision == "duplicate"
    assert r2.cached is True

    # 3. Read via absolute path
    abs_req = ReadRequest(
        raw_path=str(target_file.resolve()),
        project_root=workspace,
        root_session_id="session-alias",
        agent_invocation_id="root-inv",
        line_interval=(1, 2),
    )
    r3 = ledger.decide(abs_req)
    assert r3.decision == "duplicate"
    assert r3.cached is True

    # 4. Read via symlink if available
    if symlink_file.exists() and symlink_file.is_symlink():
        sym_req = ReadRequest(
            raw_path=str(symlink_file),
            project_root=workspace,
            root_session_id="session-alias",
            agent_invocation_id="root-inv",
            line_interval=(1, 2),
        )
        r4 = ledger.decide(sym_req)
        assert r4.decision == "duplicate"
        assert r4.canonical_path == r1.canonical_path


def test_partial_overlap_returns_missing_interval_only(workspace: Path):
    target_file = workspace / "big_file.py"
    content = "\n".join(f"# line {i}" for i in range(1, 101)) + "\n"
    target_file.write_text(content, encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-overlap",
        agent_invocation_id="root-inv",
    )

    # First: read middle range 20..50
    r1 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-overlap",
            agent_invocation_id="root-inv",
            line_interval=(20, 50),
        )
    )
    assert r1.decision == "allowed"
    assert r1.allowed_intervals == [[20, 50]]

    # Second: read full file 1..100 -> partial overlap
    r2 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-overlap",
            agent_invocation_id="root-inv",
            line_interval=(1, 100),
        )
    )
    assert r2.decision == "partial"
    assert r2.cached is False
    assert r2.reason_code == "partial_overlap"
    assert r2.allowed_intervals == [[1, 19], [51, 100]]
    assert r2.cached_intervals == [[20, 50]]

    # Third: read 1..100 again -> full duplicate now
    r3 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-overlap",
            agent_invocation_id="root-inv",
            line_interval=(1, 100),
        )
    )
    assert r3.decision == "duplicate"
    assert r3.allowed_intervals == []


def test_disjoint_ranges_merged(workspace: Path):
    target_file = workspace / "disjoint.py"
    content = "\n".join(f"# line {i}" for i in range(1, 101)) + "\n"
    target_file.write_text(content, encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-disjoint",
        agent_invocation_id="root-inv",
    )

    r1 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-disjoint",
            agent_invocation_id="root-inv",
            line_interval=(1, 10),
        )
    )
    assert r1.decision == "allowed"

    r2 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-disjoint",
            agent_invocation_id="root-inv",
            line_interval=(50, 60),
        )
    )
    assert r2.decision == "allowed"

    # Read bridging range 11..49
    r3 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-disjoint",
            agent_invocation_id="root-inv",
            line_interval=(11, 49),
        )
    )
    assert r3.decision == "allowed"

    # Now 1..60 is completely covered
    r4 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-disjoint",
            agent_invocation_id="root-inv",
            line_interval=(5, 55),
        )
    )
    assert r4.decision == "duplicate"
    assert r4.cached is True


def test_eof_and_omitted_range_handling(workspace: Path):
    target_file = workspace / "eof_file.py"
    content = "\n".join(f"# line {i}" for i in range(1, 81)) + "\n"
    target_file.write_text(content, encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-eof",
        agent_invocation_id="root-inv",
    )

    # 1. Read with end_line=None (EOF)
    r1 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-eof",
            agent_invocation_id="root-inv",
            start_line=10,
            end_line=None,
        )
    )
    assert r1.decision == "allowed"
    assert r1.allowed_intervals == [[10, 80]]

    # 2. Omitted range on existing file defaults to full file (1..80) -> partial with [1, 9] missing
    r2 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-eof",
            agent_invocation_id="root-inv",
        )
    )
    assert r2.decision == "partial"
    assert r2.allowed_intervals == [[1, 9]]
    assert r2.cached_intervals == [[10, 80]]

    # 3. Nonexistent file with omitted range and no content hash -> fail-closed
    r3 = ledger.decide(
        ReadRequest(
            raw_path=workspace / "missing.py",
            project_root=workspace,
            root_session_id="session-eof",
            agent_invocation_id="root-inv",
        )
    )
    assert r3.decision == "denied"
    assert r3.reason_code == "content_version_unknown"


def test_parent_and_child_ranges_are_actor_isolated(workspace: Path):
    target_file = workspace / "shared.py"
    target_file.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    # Root agent ledger
    root_ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-iso",
        agent_invocation_id="root-inv",
        actor_kind="root",
    )

    # Child agent ledger 1
    child_ledger_1 = ContextLedger(
        project_root=workspace,
        root_session_id="session-iso",
        agent_invocation_id="child-inv-1",
        actor_kind="subagent",
        parent_invocation_id="root-inv",
    )

    # Child agent ledger 2
    child_ledger_2 = ContextLedger(
        project_root=workspace,
        root_session_id="session-iso",
        agent_invocation_id="child-inv-2",
        actor_kind="subagent",
        parent_invocation_id="root-inv",
    )

    # 1. Root reads shared.py
    r_root_1 = root_ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-iso",
            agent_invocation_id="root-inv",
            line_interval=(1, 3),
        )
    )
    assert r_root_1.decision == "allowed"

    # 2. Child 1 reads same range -> MUST BE ALLOWED (isolated from parent)
    r_child1_1 = child_ledger_1.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-iso",
            agent_invocation_id="child-inv-1",
            line_interval=(1, 3),
        )
    )
    assert r_child1_1.decision == "allowed"
    assert r_child1_1.cached is False

    # 3. Child 1 reads again -> duplicate
    r_child1_2 = child_ledger_1.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-iso",
            agent_invocation_id="child-inv-1",
            line_interval=(1, 3),
        )
    )
    assert r_child1_2.decision == "duplicate"

    # 4. Child 2 reads same range -> MUST BE ALLOWED (isolated from Child 1)
    r_child2_1 = child_ledger_2.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-iso",
            agent_invocation_id="child-inv-2",
            line_interval=(1, 3),
        )
    )
    assert r_child2_1.decision == "allowed"

    # 5. Root reads again -> duplicate for root
    r_root_2 = root_ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-iso",
            agent_invocation_id="root-inv",
            line_interval=(1, 3),
        )
    )
    assert r_root_2.decision == "duplicate"


def test_edit_invalidates_ranges_and_unknown_hash_fails_closed(workspace: Path):
    target_file = workspace / "mutable.py"
    target_file.write_text("version 1 content\n", encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-mut",
        agent_invocation_id="root-inv",
    )

    # 1. Read version 1
    r1 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-mut",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )
    assert r1.decision == "allowed"

    # 2. Modify file on disk (external or edit write)
    target_file.write_text("version 2 modified content\nline 2\n", encoding="utf-8")

    # 3. Read again -> content hash changed -> old ranges invalidated -> allowed with new hash
    r2 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-mut",
            agent_invocation_id="root-inv",
            line_interval=(1, 2),
        )
    )
    assert r2.decision == "allowed"
    assert r2.content_hash != r1.content_hash

    # 4. Explicit invalidate call
    ledger.invalidate(target_file)
    r3 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-mut",
            agent_invocation_id="root-inv",
            line_interval=(1, 2),
        )
    )
    assert r3.decision == "allowed"

    # 5. Unknown hash / unreadable file fails closed
    r4 = ledger.decide(
        ReadRequest(
            raw_path=workspace / "does_not_exist.py",
            project_root=workspace,
            root_session_id="session-mut",
            agent_invocation_id="root-inv",
            line_interval=(1, 5),
        )
    )
    assert r4.decision == "denied"
    assert r4.reason_code == "content_version_unknown"


def test_restart_preserves_durable_duplicate_decision(workspace: Path):
    target_file = workspace / "persist.py"
    target_file.write_text("persistent content\n", encoding="utf-8")

    # Process 1 instance
    ledger1 = ContextLedger(
        project_root=workspace,
        root_session_id="session-persist",
        agent_invocation_id="root-inv",
    )
    r1 = ledger1.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-persist",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )
    assert r1.decision == "allowed"

    # Verify JSON file was created on disk
    ledger_file = ledger1.ledger_path
    assert ledger_file.is_file()

    # Verify NO source content stored in JSON
    raw_json = ledger_file.read_text(encoding="utf-8")
    assert "persistent content" not in raw_json
    data = json.loads(raw_json)
    assert "files" in data
    assert "counters" in data
    assert "records" in data

    # Process 2 instance (fresh object loading from disk)
    ledger2 = ContextLedger(
        project_root=workspace,
        root_session_id="session-persist",
        agent_invocation_id="root-inv",
    )
    r2 = ledger2.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-persist",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )
    assert r2.decision == "duplicate"
    assert r2.cached is True


def test_atomic_persistence_and_file_lock(workspace: Path):
    target_file = workspace / "lock_test.py"
    target_file.write_text("content\n", encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-lock",
        agent_invocation_id="root-inv",
    )
    ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-lock",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )

    assert ledger.ledger_path.is_file()
    assert ledger.lock_path.is_file()

    # Test lock acquisition
    with _LedgerFileLock(ledger.lock_path, timeout=1.0):
        # Lock acquired successfully
        pass


def test_concurrent_decide_and_edit_invalidation(workspace: Path):
    target_file = workspace / "concurrent.py"
    target_file.write_text("v1\n", encoding="utf-8")

    ledger = ContextLedger(
        project_root=workspace,
        root_session_id="session-concurrent",
        agent_invocation_id="root-inv",
    )
    r1 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-concurrent",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )
    assert r1.decision == "allowed"

    # Record edit
    target_file.write_text("v2\n", encoding="utf-8")
    ledger.record_edit(target_file)

    r2 = ledger.decide(
        ReadRequest(
            raw_path=target_file,
            project_root=workspace,
            root_session_id="session-concurrent",
            agent_invocation_id="root-inv",
            line_interval=(1, 1),
        )
    )
    assert r2.decision == "allowed"
    assert r2.content_hash != r1.content_hash


def test_interval_algebra_pure_functions():
    # normalize_intervals
    assert normalize_intervals([[1, 10], [5, 15]]) == [[1, 15]]
    assert normalize_intervals([[1, 10], [11, 20]]) == [[1, 20]]
    assert normalize_intervals([[1, 10], [15, 20]]) == [[1, 10], [15, 20]]

    # interval_subtract
    missing, covered = interval_subtract((1, 100), [[20, 50]])
    assert missing == [[1, 19], [51, 100]]
    assert covered == [[20, 50]]

    missing, covered = interval_subtract((1, 10), [[1, 100]])
    assert missing == []
    assert covered == [[1, 10]]

    missing, covered = interval_subtract((50, 60), [[1, 10], [70, 80]])
    assert missing == [[50, 60]]
    assert covered == []

    # interval_union
    assert interval_union([[1, 10], [50, 60]], [[11, 49]]) == [[1, 60]]
