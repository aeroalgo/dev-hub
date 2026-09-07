"""Tests for ContextLedger adapters, provider parity, and invalidation semantics.
Addresses FR-002, FR-007, FR-008, FR-009, FR-010.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from context_ledger import (
    ActorKey,
    ContextLedger,
    DecisionReceipt,
    ReadRequest,
    canonicalize_path,
    compute_content_hash,
)
from context_ledger_adapters import (
    READ_TOOL_ALIASES,
    WRITE_TOOL_ALIASES,
    NormalizedReadPayload,
    NormalizedWritePayload,
    evaluate_read_payload,
    evaluate_write_payload,
    format_claude_response,
    format_codex_response,
    generate_derived_identity,
    invalidate_session_actors,
    normalize_read_payload,
    normalize_write_payload,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_claude_and_codex_aliases_share_normalized_receipt(workspace: Path):
    target = workspace / "module.py"
    target.write_text("line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nline 8\nline 9\nline 10\n", encoding="utf-8")

    claude_payload = {
        "tool_name": "Read",
        "tool_input": {
            "file_path": "module.py",
            "offset": 2,
            "limit": 4,  # lines 2..5
        },
        "session_id": "shared-session-1",
        "tool_use_id": "inv-001",
        "actor_kind": "root",
        "cwd": str(workspace),
    }

    codex_payload = {
        "tool": "read",
        "arguments": {
            "path": "module.py",
            "start_line": 2,
            "end_line": 5,  # lines 2..5
        },
        "session_id": "shared-session-1",
        "invocation_id": "inv-001",
        "actor_kind": "root",
        "cwd": str(workspace),
    }

    norm_claude = normalize_read_payload(claude_payload, default_cwd=workspace)
    norm_codex = normalize_read_payload(codex_payload, default_cwd=workspace)

    assert norm_claude.raw_path == "module.py"
    assert norm_codex.raw_path == "module.py"
    assert norm_claude.start_line == 2 and norm_claude.end_line == 5
    assert norm_codex.start_line == 2 and norm_codex.end_line == 5
    assert norm_claude.root_session_id == norm_codex.root_session_id
    assert norm_claude.agent_invocation_id == norm_codex.agent_invocation_id

    # Evaluate receipts
    runtime_dir = workspace / ".runtime"
    receipt_claude, resp_claude = evaluate_read_payload(
        claude_payload, cwd=workspace, runtime_dir=runtime_dir
    )

    # Clean ledger for fair comparison of first-read receipt
    ledger_file = runtime_dir / "context-ledger"
    if ledger_file.exists():
        import shutil
        shutil.rmtree(ledger_file)

    receipt_codex, resp_codex = evaluate_read_payload(
        codex_payload, cwd=workspace, runtime_dir=runtime_dir
    )

    assert receipt_claude.decision == receipt_codex.decision == "allowed"
    assert receipt_claude.reason_code == receipt_codex.reason_code == "uncached_interval"
    assert receipt_claude.canonical_path == receipt_codex.canonical_path == str(target.resolve())
    assert receipt_claude.requested_intervals == receipt_codex.requested_intervals == [[2, 5]]
    assert receipt_claude.allowed_intervals == receipt_codex.allowed_intervals == [[2, 5]]
    assert receipt_claude.cached_intervals == receipt_codex.cached_intervals == []
    assert receipt_claude.cached == receipt_codex.cached == False

    # Responses contain transport-specific mappings
    assert resp_claude["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert resp_codex["decision"] == "allowed"
    assert resp_codex["allow"] is True
    assert resp_codex["exit_code"] == 0


def test_root_write_invalidates_subagent_ranges(workspace: Path):
    target = workspace / "shared_data.py"
    target.write_text("v1 line 1\nv1 line 2\nv1 line 3\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"
    session_id = "cross-actor-session"

    # Step 1: Root actor reads 1..3 -> allowed
    root_read_payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "shared_data.py", "start_line": 1, "end_line": 3},
        "session_id": session_id,
        "agent_invocation_id": "root-actor",
        "actor_kind": "root",
        "cwd": str(workspace),
    }
    r_receipt1, _ = evaluate_read_payload(root_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert r_receipt1.decision == "allowed"

    # Step 2: Root actor reads again -> duplicate
    r_receipt2, _ = evaluate_read_payload(root_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert r_receipt2.decision == "duplicate"
    assert r_receipt2.reason_code == "duplicate_range"

    # Step 3: Subagent actor reads 1..3 -> allowed (independent lineage)
    sub_read_payload = {
        "tool_name": "ReadFile",
        "tool_input": {"file_path": "shared_data.py", "start_line": 1, "end_line": 3},
        "session_id": session_id,
        "agent_invocation_id": "subagent-worker-1",
        "actor_kind": "subagent",
        "parent_invocation_id": "root-actor",
        "cwd": str(workspace),
    }
    s_receipt1, _ = evaluate_read_payload(sub_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert s_receipt1.decision == "allowed"

    # Step 4: Subagent reads again -> duplicate
    s_receipt2, _ = evaluate_read_payload(sub_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert s_receipt2.decision == "duplicate"

    # Step 5: Root performs a write modifying the file
    new_content = "v2 updated 1\nv2 updated 2\nv2 updated 3\n"
    target.write_text(new_content, encoding="utf-8")
    root_write_payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "shared_data.py", "contents": new_content},
        "session_id": session_id,
        "agent_invocation_id": "root-actor",
        "actor_kind": "root",
        "cwd": str(workspace),
    }
    ok, reason, _ = evaluate_write_payload(root_write_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert ok is True
    assert reason == "write_invalidated"

    # Step 6: Subagent reads 1..3 again -> allowed (invalidated and hash updated!)
    s_receipt3, _ = evaluate_read_payload(sub_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert s_receipt3.decision == "allowed"
    assert s_receipt3.reason_code == "uncached_interval"

    # Step 7: Subagent reads again -> duplicate on v2
    s_receipt4, _ = evaluate_read_payload(sub_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert s_receipt4.decision == "duplicate"

    # Step 8: Root reads 1..3 -> allowed once on v2
    r_receipt3, _ = evaluate_read_payload(root_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert r_receipt3.decision == "allowed"

    # Step 9: Root reads again -> duplicate on v2
    r_receipt4, _ = evaluate_read_payload(root_read_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert r_receipt4.decision == "duplicate"


def test_missing_invocation_identity_is_derived_and_recorded(workspace: Path):
    target = workspace / "script.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"

    payload_no_inv = {
        "tool_name": "Read",
        "tool_input": {"file_path": "script.py", "start_line": 1, "end_line": 1},
        "session_id": "sess-no-inv",
        "cwd": str(workspace),
    }

    norm = normalize_read_payload(payload_no_inv, default_cwd=workspace)
    assert norm.derived_identity is True
    assert norm.agent_invocation_id.startswith("derived_identity_")
    assert norm.metadata.get("derived_identity") is True

    # Same parameters produce deterministic derived_identity
    norm2 = normalize_read_payload(payload_no_inv, default_cwd=workspace)
    assert norm.agent_invocation_id == norm2.agent_invocation_id

    receipt, _ = evaluate_read_payload(payload_no_inv, cwd=workspace, runtime_dir=runtime_dir)
    assert receipt.decision == "allowed"
    assert receipt.metadata.get("derived_identity") is True


def test_provider_mismatch_fails_closed_without_local_fallback(workspace: Path):
    runtime_dir = workspace / ".runtime"

    # Malformed payload: missing file_path
    malformed_payload = {
        "tool_name": "Read",
        "tool_input": {},
        "session_id": "sess-malformed",
        "cwd": str(workspace),
    }

    receipt, resp = evaluate_read_payload(malformed_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert receipt.decision == "denied"
    assert receipt.reason_code == "payload_divergence_denied"
    assert receipt.metadata.get("fail_closed") is True
    assert resp["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_read_and_write_tool_aliases_normalized_identically(workspace: Path):
    target = workspace / "alias_test.py"
    target.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"

    read_aliases = ["Read", "read", "ReadFile", "read_file", "View", "view", "file_read"]
    for i, alias in enumerate(read_aliases):
        p = {
            "tool_name": alias,
            "tool_input": {"file_path": "alias_test.py", "offset": 1, "limit": 2},
            "session_id": f"sess-alias-{i}",
            "agent_invocation_id": "inv-1",
            "cwd": str(workspace),
        }
        norm = normalize_read_payload(p, default_cwd=workspace)
        assert norm.start_line == 1
        assert norm.end_line == 2
        assert norm.raw_path == "alias_test.py"

    write_aliases = ["Write", "write", "Edit", "edit", "NotebookEdit", "apply_patch"]
    for i, alias in enumerate(write_aliases):
        p = {
            "tool_name": alias,
            "tool_input": {"path": "alias_test.py", "contents": "a = 99\n"},
            "session_id": f"sess-w-alias-{i}",
            "agent_invocation_id": "inv-1",
            "cwd": str(workspace),
        }
        norm = normalize_write_payload(p, default_cwd=workspace)
        assert norm.raw_path == "alias_test.py"
        assert norm.new_content == "a = 99\n"


def test_whole_file_missing_range_resolves_total_lines(workspace: Path):
    target = workspace / "full.py"
    target.write_text("1\n2\n3\n4\n5\n6\n7\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"

    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "full.py"},  # no range specified
        "session_id": "sess-full-read",
        "agent_invocation_id": "inv-full",
        "cwd": str(workspace),
    }

    receipt, _ = evaluate_read_payload(payload, cwd=workspace, runtime_dir=runtime_dir)
    assert receipt.decision == "allowed"
    assert receipt.requested_intervals == [[1, 7]]
    assert receipt.allowed_intervals == [[1, 7]]


def test_rename_and_delete_invalidation(workspace: Path):
    old_f = workspace / "old.py"
    old_f.write_text("old content\n", encoding="utf-8")
    new_f = workspace / "new.py"
    new_f.write_text("new content\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"
    session_id = "rename-session"

    # Read old.py and new.py
    evaluate_read_payload(
        {"tool_name": "Read", "tool_input": {"file_path": "old.py", "start_line": 1, "end_line": 1}, "session_id": session_id, "agent_invocation_id": "actor-1", "cwd": str(workspace)},
        cwd=workspace, runtime_dir=runtime_dir
    )
    evaluate_read_payload(
        {"tool_name": "Read", "tool_input": {"file_path": "new.py", "start_line": 1, "end_line": 1}, "session_id": session_id, "agent_invocation_id": "actor-1", "cwd": str(workspace)},
        cwd=workspace, runtime_dir=runtime_dir
    )

    # Rename old.py -> new.py
    rename_payload = {
        "tool_name": "rename_file",
        "tool_input": {"old_path": "old.py", "new_path": "new.py", "path": "new.py"},
        "session_id": session_id,
        "agent_invocation_id": "actor-1",
        "cwd": str(workspace),
    }
    ok, reason, _ = evaluate_write_payload(rename_payload, cwd=workspace, runtime_dir=runtime_dir)
    assert ok is True
    assert reason == "write_invalidated"
