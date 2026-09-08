"""Tests for ContextScope, ScopeResolver, search allowlist, and plan jump context policy.
Addresses FR-003, FR-004, TM-078-03, TM-078-04.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from context_scope import (
    ScopeResolver,
    is_search_command_line,
)
from loop.mb_load.plan_section import (
    evaluate_plan_read,
    is_whole_plan_path,
    materialize_plan_jump,
    parse_plan_jump,
)
from context_ledger_adapters import (
    evaluate_read_payload,
    format_claude_response,
    format_codex_response,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


def test_implement_whole_plan_denied_and_plan_jump_allowed(workspace: Path):
    plan_dir = workspace / "memory-bank" / "back" / "plan" / "T-HUB-078" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"
    plan_file.write_text(
        "\n".join(f"line {i}: content for plan" for i in range(1, 200)),
        encoding="utf-8",
    )

    declared_jumps = [
        "memory-bank/back/plan/T-HUB-078/md/plan.md:84-115",
        "memory-bank/back/plan/T-HUB-078/md/plan.md:150-180",
    ]

    # 1. Whole plan read in IMPLEMENT mode without line range is DENIED
    allowed, reason, details = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-078/md/plan.md",
        start_line=None,
        end_line=None,
        mode="IMPLEMENT",
        declared_jumps=declared_jumps,
        project_root=workspace,
    )
    assert not allowed
    assert reason == "whole_plan_denied"
    assert "Whole plan read denied in IMPLEMENT" in details["diagnostic"]
    assert details["fail_closed"] is True

    # 2. Plan jump matching declared range is ALLOWED
    allowed, reason, details = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-078/md/plan.md",
        start_line=84,
        end_line=115,
        mode="IMPLEMENT",
        declared_jumps=declared_jumps,
        project_root=workspace,
    )
    assert allowed
    assert reason == "plan_jump_allowed"
    assert details["excerpt_identity"] == "memory-bank/back/plan/T-HUB-078/md/plan.md:84-115"
    assert details["matched_jump"] == "memory-bank/back/plan/T-HUB-078/md/plan.md:84-115"

    # 3. Whole plan read in DECOMPOSE/PLAN mode is ALLOWED
    allowed_decompose, reason_dec, _ = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-078/md/plan.md",
        start_line=None,
        end_line=None,
        mode="DECOMPOSE",
        project_root=workspace,
    )
    assert allowed_decompose
    assert reason_dec == "plan_mode_allowed"

    allowed_plan, reason_plan, _ = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-078/md/plan.md",
        start_line=None,
        end_line=None,
        mode="PLAN",
        project_root=workspace,
    )
    assert allowed_plan
    assert reason_plan == "plan_mode_allowed"

    # 4. Whole plan read with explicit exception_reason in IMPLEMENT is ALLOWED
    allowed_exc, reason_exc, details_exc = evaluate_plan_read(
        path="memory-bank/back/plan/T-HUB-078/md/plan.md",
        start_line=None,
        end_line=None,
        mode="IMPLEMENT",
        exception_reason="Debugging architectural discrepancy with human approval",
        project_root=workspace,
    )
    assert allowed_exc
    assert reason_exc == "exception_approved"


def test_evaluate_read_payload_blocks_whole_plan_and_permits_jump(workspace: Path):
    plan_dir = workspace / "memory-bank" / "back" / "plan" / "T-HUB-078" / "md"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan.md"
    plan_file.write_text(
        "\n".join(f"line {i}: content" for i in range(1, 150)),
        encoding="utf-8",
    )

    # Whole plan read attempt in Claude format
    claude_payload = {
        "tool_name": "Read",
        "tool_input": {
            "file_path": "memory-bank/back/plan/T-HUB-078/md/plan.md",
        },
        "session_id": "sess-plan-1",
        "cwd": str(workspace),
    }

    receipt, resp = evaluate_read_payload(claude_payload, provider="claude", cwd=workspace)
    assert receipt.decision == "denied"
    assert receipt.reason_code == "whole_plan_denied"
    assert resp["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert resp["hookSpecificOutput"]["permissionDecisionReason"] == "whole_plan_denied"
    assert "Whole plan read denied in IMPLEMENT" in resp["hookSpecificOutput"]["additionalContext"]

    # Plan jump read attempt in Claude format
    claude_jump_payload = {
        "tool_name": "Read",
        "tool_input": {
            "file_path": "memory-bank/back/plan/T-HUB-078/md/plan.md",
            "offset": 84,
            "limit": 32,  # lines 84..115
        },
        "session_id": "sess-plan-1",
        "cwd": str(workspace),
    }

    jump_receipt, jump_resp = evaluate_read_payload(claude_jump_payload, provider="claude", cwd=workspace)
    assert jump_receipt.decision == "allowed"
    assert jump_resp["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_search_scope_requires_graphify_exception(workspace: Path):
    shard_file = workspace / "step.yaml"
    shard_data = {
        "files": [
            "loop/mb_load/plan_section.py",
            "harness/hooks/context_scope.py",
        ],
        "delta": [
            "ADD ContextScope request in `harness/hooks/context_scope.py`",
            "EDIT `loop/mb_load/plan_section.py` to support plan jumps",
        ],
        "plan_contract": {
            "layout_paths": ["loop/mb_load/plan_section.py"],
            "plan_jumps": ["memory-bank/back/plan/T-HUB-078/md/plan.md:84-115"],
        },
    }
    shard_file.write_text(yaml.dump(shard_data), encoding="utf-8")

    resolver = ScopeResolver(project_root=workspace, shard_data=shard_data)

    # 1. Search inside allowlist path is ALLOWED
    ok, reason, details = resolver.evaluate_search("rg -n 'def ' loop/mb_load/plan_section.py")
    assert ok
    assert reason == "search_inside_scope"

    # 2. Search inside allowed parent directory is ALLOWED
    ok_dir, reason_dir, _ = resolver.evaluate_search("rg 'class' harness/hooks/")
    assert ok_dir
    assert reason_dir == "search_inside_scope"

    # 3. Broad search on entire repo without graphify evidence is DENIED
    ok_broad, reason_broad, details_broad = resolver.evaluate_search("rg 'some_pattern'")
    assert not ok_broad
    assert reason_broad == "search_outside_scope_denied"
    assert details_broad["fail_closed"] is True

    # 4. Search on outside directory without graphify is DENIED
    ok_out, reason_out, details_out = resolver.evaluate_search("rg 'pattern' other_pkg/unknown.py")
    assert not ok_out
    assert reason_out == "search_outside_scope_denied"

    # 5. Search on outside directory with graphify evidence AND typed reason is ALLOWED
    ok_exc, reason_exc, details_exc = resolver.evaluate_search(
        "rg 'pattern' other_pkg/unknown.py",
        graphify_evidence="graphify query 'other_pkg' returned 3 symbols",
        exception_reason="Investigating external dependency linkage",
    )
    assert ok_exc
    assert reason_exc == "graphify_exception_approved"


def test_tool_aliases_cannot_bypass_search_scope(workspace: Path):
    shard_data = {
        "files": ["app/core/service.py"],
        "delta": ["EDIT `app/core/service.py`"],
    }
    resolver = ScopeResolver(project_root=workspace, shard_data=shard_data)

    # Aliases: grep, find, cat, python reading outside scope
    aliases = [
        "grep -rn 'foo' secret_dir/",
        "find unlisted_dir/ -name '*.py'",
        "cat secret_config.json",
        "python -c \"open('unlisted/file.txt').read()\"",
    ]

    for cmd in aliases:
        assert is_search_command_line(cmd)
        ok, reason, details = resolver.evaluate_search(cmd)
        assert not ok, f"Command {cmd} should have been denied"
        assert reason == "search_outside_scope_denied"


@pytest.mark.parametrize("cmd", [
    "git log -S verify_hints -p harness/hooks/epic_yaml.py",
    "git grep verify_hints",
])
def test_git_history_and_grep_are_search_commands(cmd: str) -> None:
    assert is_search_command_line(cmd)
