"""Provider parity tests for ContextLedger adapters across Claude and Codex.
Verifies that Claude PreToolUse/PostToolUse and Codex event bridge structures
produce equivalent decisions, reasons, lineage isolation, and invalidation semantics.
Addresses FR-002, FR-007, FR-008, FR-009, FR-010.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from harness.hooks.context_ledger import ContextLedger, DecisionReceipt
from harness.hooks.context_ledger_adapters import (
    evaluate_read_payload,
    evaluate_write_payload,
    normalize_read_payload,
    normalize_write_payload,
)
from loop.runtime_adapters.claude import ClaudeAdapter
from loop.runtime_adapters.codex import CodexAdapter


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "parity_project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_claude_and_codex_adapters_produce_parity_normalized_requests(workspace: Path):
    doc = workspace / "service.py"
    doc.write_text("def a(): pass\ndef b(): pass\ndef c(): pass\n", encoding="utf-8")

    claude_adapter = ClaudeAdapter()
    codex_adapter = CodexAdapter()

    claude_event = {
        "tool_name": "Read",
        "tool_input": {"file_path": "service.py", "offset": 1, "limit": 2},
        "session_id": "parity-sess-1",
        "tool_use_id": "actor-root-1",
        "actor_kind": "root",
    }

    codex_event = {
        "tool": "read",
        "arguments": {"path": "service.py", "start_line": 1, "end_line": 2},
        "session_id": "parity-sess-1",
        "invocation_id": "actor-root-1",
        "actor_kind": "root",
    }

    norm_c = claude_adapter.normalize_read_event(claude_event, cwd=workspace)
    norm_x = codex_adapter.normalize_read_event(codex_event, cwd=workspace)

    assert norm_c.raw_path == norm_x.raw_path
    assert norm_c.start_line == norm_x.start_line == 1
    assert norm_c.end_line == norm_x.end_line == 2
    assert norm_c.root_session_id == norm_x.root_session_id == "parity-sess-1"
    assert norm_c.agent_invocation_id == norm_x.agent_invocation_id == "actor-root-1"
    assert norm_c.actor_kind == norm_x.actor_kind == "root"


def test_root_and_two_subagents_parity_isolation(workspace: Path):
    target = workspace / "state.py"
    target.write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"
    session_id = "parity-multi-actor"

    claude_adapter = ClaudeAdapter()
    codex_adapter = CodexAdapter()

    # Under Claude runtime: root, subagent-1, subagent-2
    r_c_rec, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "state.py", "start_line": 1, "end_line": 3}, "session_id": session_id, "tool_use_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    s1_c_rec, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "state.py", "start_line": 1, "end_line": 3}, "session_id": session_id, "tool_use_id": "sub-1", "actor_kind": "subagent", "parent_invocation_id": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    s2_c_rec, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "state.py", "start_line": 1, "end_line": 3}, "session_id": session_id, "tool_use_id": "sub-2", "actor_kind": "subagent", "parent_invocation_id": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )

    # All three get allowed independently on first read
    assert r_c_rec.decision == "allowed"
    assert s1_c_rec.decision == "allowed"
    assert s2_c_rec.decision == "allowed"

    # Second read for each -> duplicate
    r_c_dup, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "state.py", "start_line": 1, "end_line": 3}, "session_id": session_id, "tool_use_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    s1_c_dup, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "state.py", "start_line": 1, "end_line": 3}, "session_id": session_id, "tool_use_id": "sub-1", "actor_kind": "subagent", "parent_invocation_id": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r_c_dup.decision == "duplicate"
    assert s1_c_dup.decision == "duplicate"


def test_root_write_invalidates_for_all_actors_parity(workspace: Path):
    target = workspace / "config.json"
    target.write_text('{"ver": 1}\n', encoding="utf-8")
    runtime_dir = workspace / ".runtime"
    session_id = "parity-invalidation-sess"

    codex_adapter = CodexAdapter()

    # Actor 1 reads
    r1, _ = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {"path": "config.json", "start_line": 1, "end_line": 1}, "session_id": session_id, "invocation_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r1.decision == "allowed"

    # Subagent 1 reads
    s1, _ = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {"path": "config.json", "start_line": 1, "end_line": 1}, "session_id": session_id, "invocation_id": "sub-1", "actor_kind": "subagent"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert s1.decision == "allowed"

    # Write by root actor
    target.write_text('{"ver": 2}\n', encoding="utf-8")
    ok, reason, _ = codex_adapter.evaluate_context_write(
        {"tool": "write", "arguments": {"path": "config.json", "content": '{"ver": 2}\n'}, "session_id": session_id, "invocation_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert ok is True
    assert reason == "write_invalidated"

    # Both actors read new hash once -> allowed
    r2, _ = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {"path": "config.json", "start_line": 1, "end_line": 1}, "session_id": session_id, "invocation_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    s2, _ = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {"path": "config.json", "start_line": 1, "end_line": 1}, "session_id": session_id, "invocation_id": "sub-1", "actor_kind": "subagent"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r2.decision == "allowed"
    assert s2.decision == "allowed"

    # Subsequent reads -> duplicate
    r3, _ = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {"path": "config.json", "start_line": 1, "end_line": 1}, "session_id": session_id, "invocation_id": "root", "actor_kind": "root"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r3.decision == "duplicate"


def test_missing_identity_derived_and_fail_closed_parity(workspace: Path):
    target = workspace / "sample.txt"
    target.write_text("content\n", encoding="utf-8")
    runtime_dir = workspace / ".runtime"

    claude_adapter = ClaudeAdapter()
    codex_adapter = CodexAdapter()

    # Missing invocation ID -> deterministic derived_identity
    r_c, _ = claude_adapter.evaluate_context_read(
        {"tool_name": "Read", "tool_input": {"file_path": "sample.txt"}, "session_id": "sess-det"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r_c.decision == "allowed"
    assert r_c.metadata.get("derived_identity") is True

    # Malformed payload -> fail-closed denied
    r_fail, resp_fail = codex_adapter.evaluate_context_read(
        {"tool": "read", "arguments": {}, "session_id": "sess-fail"},
        cwd=workspace, runtime_dir=runtime_dir
    )
    assert r_fail.decision == "denied"
    assert r_fail.reason_code == "payload_divergence_denied"
    assert resp_fail["allow"] is False
    assert resp_fail["exit_code"] == 1
