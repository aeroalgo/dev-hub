"""Production shard flow regression test for context budget enforcement.

Verifies that a real shard flow executes through production entrypoints
(prompt projection, ScopeResolver, ContextLedger, and finish telemetry)
with an allowed code map, bounded plan-jumps, a full TDD edit/re-read cycle,
zero duplicate full reads, and an attributable finish receipt.
Addresses FR-003, FR-004, FR-007, FR-008, FR-010 (Checkpoint cp3).
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from harness.hooks.context_ledger import ContextLedger
from harness.hooks.context_ledger_adapters import (
    evaluate_read_payload,
    evaluate_write_payload,
    normalize_read_payload,
    normalize_write_payload,
)
from harness.hooks.context_scope import (
    ScopeResolver,
    compute_test_fingerprint,
    normalize_test_command,
)
from harness.hooks.context_telemetry import (
    build_finish_receipt,
    collect_session_telemetry,
    verify_telemetry_secret_free,
)
from loop.mb_load.plan_section import evaluate_plan_read, materialize_plan_jump


@pytest.fixture
def shard_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "shard_proj"
    ws.mkdir(parents=True, exist_ok=True)

    # 1. Create project source and test files
    app_dir = ws / "app"
    app_dir.mkdir(parents=True)
    calc_file = app_dir / "calculator.py"
    calc_file.write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")

    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_calculator.py"
    test_file.write_text(
        "from app.calculator import add, sub\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    # 2. Create whole plan and shard files
    plan_dir = ws / "memory-bank/back/plan/T-HUB-099/md"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / "plan.md"
    plan_lines = ["# Plan header\n", "## Architecture\n"] + [f"Plan detail line {i}\n" for i in range(1, 100)]
    plan_file.write_text("".join(plan_lines), encoding="utf-8")

    steps_dir = ws / "memory-bank/back/plan/T-HUB-099/yaml/steps"
    steps_dir.mkdir(parents=True)
    shard_file = steps_dir / "s01-calculator.yaml"
    shard_content = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "T-HUB-099",
        "title": "Implement calculator operations",
        "next_phase": "BACK IMPLEMENT",
        "files": ["app/calculator.py", "tests/test_calculator.py"],
        "plan_contract": {
            "plan_jumps": ["memory-bank/back/plan/T-HUB-099/md/plan.md:10-25"],
        },
    }
    shard_file.write_text(yaml.safe_dump(shard_content), encoding="utf-8")

    return ws


def test_real_shard_flow_has_bounded_plan_and_no_duplicate_read(shard_workspace: Path):
    """Regression test cp3: Complete real shard flow with bounded plan, scope, TDD cycle, and finish receipt."""
    ws = shard_workspace
    shard_yaml_path = ws / "memory-bank/back/plan/T-HUB-099/yaml/steps/s01-calculator.yaml"
    shard_data = yaml.safe_load(shard_yaml_path.read_text(encoding="utf-8"))

    # Stage 1: Prompt Projection & Plan Bounds Check
    # Attempting to read whole plan without bounds in IMPLEMENT mode is denied
    allowed, reason, details = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-099/md/plan.md",
        start_line=None,
        end_line=None,
        mode="BACK IMPLEMENT",
    )
    assert not allowed
    assert reason == "whole_plan_denied"

    # Materialize bounded plan jump
    jump_str = shard_data["plan_contract"]["plan_jumps"][0]
    jump_result = materialize_plan_jump(jump_str, cwd=ws)
    assert jump_result["ok"] is True
    assert jump_result["line_count"] == 16
    assert "Plan detail line" in jump_result["content"]

    # Stage 2: Scope Preflight
    scope_resolver = ScopeResolver(
        project_root=ws,
        shard_path=shard_yaml_path,
        shard_data=shard_data,
    )

    # In-scope files are allowed
    assert scope_resolver.is_path_allowed("app/calculator.py")
    assert scope_resolver.is_path_allowed("tests/test_calculator.py")

    # Out-of-scope search command without graphify receipt is denied
    search_allowed, search_reason, _ = scope_resolver.evaluate_search("rg foo other_unrelated_dir")
    assert not search_allowed
    assert search_reason == "search_outside_scope_denied"

    # Search with graphify evidence is approved
    search_ev_allowed, search_ev_reason, _ = scope_resolver.evaluate_search(
        "rg foo other_unrelated_dir",
        graphify_evidence="graphify:node-123",
        exception_reason="locating caller graph",
    )
    assert search_ev_allowed
    assert search_ev_reason == "graphify_exception_approved"

    # Stage 3: ContextLedger & TDD Cycle Enforcement
    session_id = "sess-real-flow-1"

    # Step 3.1: Read initial calculator file (lines 1..10) -> ALLOW
    claude_read_event = {
        "tool_name": "Read",
        "tool_input": {"file_path": "app/calculator.py", "offset": 1, "limit": 10},
        "session_id": session_id,
        "tool_use_id": "root-invoc-1",
        "actor_kind": "root",
    }
    receipt_read1, resp_read1 = evaluate_read_payload(claude_read_event, cwd=ws)
    assert receipt_read1.decision == "allowed"
    assert resp_read1["hookSpecificOutput"]["permissionDecision"] == "allow"

    # Step 3.2: Duplicate Read of same unchanged range -> DENY / CACHED
    receipt_dup, resp_dup = evaluate_read_payload(claude_read_event, cwd=ws)
    assert receipt_dup.decision in ("duplicate", "denied")
    assert resp_dup["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert receipt_dup.reason_code in ("duplicate_range", "cached_reference")

    # Step 3.3: TDD Write to update calculator implementation
    new_code = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n\ndef mul(a, b):\n    return a * b\n"
    (ws / "app/calculator.py").write_text(new_code, encoding="utf-8")

    claude_write_event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "app/calculator.py", "content": new_code},
        "session_id": session_id,
        "tool_use_id": "root-invoc-2",
        "actor_kind": "root",
    }
    allowed_write, reason_write, resp_write = evaluate_write_payload(claude_write_event, cwd=ws)
    assert allowed_write is True

    # Step 3.4: Re-read after edit -> ALLOW because content hash changed
    claude_reread_event = {
        "tool_name": "Read",
        "tool_input": {"file_path": "app/calculator.py", "offset": 1, "limit": 10},
        "session_id": session_id,
        "tool_use_id": "root-invoc-3",
        "actor_kind": "root",
    }
    receipt_reread, resp_reread = evaluate_read_payload(claude_reread_event, cwd=ws)
    assert receipt_reread.decision in ("allowed", "invalidated")
    assert resp_reread["hookSpecificOutput"]["permissionDecision"] == "allow"

    # Step 3.5: Execute test command with fingerprinting
    test_fp = compute_test_fingerprint(
        command=".venv/bin/pytest tests/test_calculator.py -q",
        project_root=ws,
        relevant_paths=["app/calculator.py", "tests/test_calculator.py"],
    )
    assert test_fp and len(test_fp) == 64

    # Stage 4: Finish Telemetry & Attributable Receipt
    receipt = build_finish_receipt(
        project_root=ws,
        session_id=session_id,
        epic_id="T-HUB-099",
        step_id="s01",
    )

    assert receipt.schema_version == "context-finish-receipt/v1"
    assert receipt.session_id == session_id
    assert receipt.epic_id == "T-HUB-099"
    assert receipt.step_id == "s01"
    assert receipt.status == "green"
    assert receipt.aggregate.unique_reads >= 2
    assert receipt.aggregate.duplicate_reads >= 1
    assert receipt.aggregate.total_requests >= 3
    assert len(receipt.aggregate.actors) >= 1

    # Verify receipt is completely free of sensitive source content
    receipt_dict = receipt.model_dump(by_alias=True)
    secret_free, violations = verify_telemetry_secret_free(receipt_dict)
    assert secret_free, f"Telemetry contains leaked content: {violations}"
