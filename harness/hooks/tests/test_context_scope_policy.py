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
    TestFingerprintCache,
    normalize_test_command,
    compute_test_fingerprint,
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
from hook_dispatch import (
    DecisionEnvelope,
    DiagnosticCode,
    EventContext,
    PreToolUse,
)
from pretool_policy import (
    BashPolicyAdapter,
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


# ============================================================================
# T-HUB-100 / I2: Search Scope outside EPIC_LOOP & TestFingerprintCache PreTool
# ============================================================================

def test_is_context_policy_active(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """FR-001 / TM-I2-078-03: is_context_policy_active returns True when ledger/activeContext loaded, False when unconfigured."""
    import context_ledger
    is_context_policy_active = getattr(context_ledger, "is_context_policy_active", None)
    assert is_context_policy_active is not None, "is_context_policy_active function must be defined in context_ledger"

    monkeypatch.delenv("EPIC_LOOP", raising=False)

    # 1. Unconfigured workspace -> False
    assert not is_context_policy_active(workspace)

    # 2. Workspace with activeContext.md -> True
    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    act_file = mb_dir / "activeContext.md"
    act_file.write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")
    assert is_context_policy_active(workspace)

    # 3. Workspace without activeContext.md but with active context-ledger -> True
    act_file.unlink()
    assert not is_context_policy_active(workspace)
    ledger_file = workspace / ".runtime" / "context-ledger" / "proj" / "sess" / "root.json"
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    ledger_file.write_text('{"schema": "context-ledger/v1"}', encoding="utf-8")
    assert is_context_policy_active(workspace)


def test_search_outside_scope_non_loop(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """TM-I2-078-03 / FR-001, FR-004: When context policy is active outside EPIC_LOOP,
    search command outside shard allowlist is denied with search_outside_scope_denied."""
    monkeypatch.delenv("EPIC_LOOP", raising=False)

    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    step_dir = mb_dir / "back" / "plan" / "T-HUB-100" / "yaml" / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    shard_path = step_dir / "s01.yaml"
    shard_path.write_text(
        yaml.dump({
            "files": ["harness/hooks/context_scope.py"],
            "delta": ["EDIT harness/hooks/context_scope.py"],
        }),
        encoding="utf-8",
    )

    adapter = BashPolicyAdapter()
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "rg 'pattern' outside/unknown.py"},
        cwd=workspace,
        session_id="test-sess-search-non-loop",
        raw_payload={
            "tool_name": "Bash",
            "tool_input": {"command": "rg 'pattern' outside/unknown.py"},
            "cwd": str(workspace),
            "session_id": "test-sess-search-non-loop",
        },
    )

    env = adapter.evaluate(ctx)
    assert env is not None, "Expected search outside allowlist to be denied when context policy is active"
    assert env.is_deny
    assert "search_outside_scope_denied" in (env.reason or "")


def test_search_outside_scope_deny_non_loop(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """TM-I2-078-03 / TM-I2-078-05: Subagents with derived identity receive identical search deny outside scope."""
    monkeypatch.delenv("EPIC_LOOP", raising=False)

    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    step_dir = mb_dir / "back" / "plan" / "T-HUB-100" / "yaml" / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    shard_path = step_dir / "s01.yaml"
    shard_path.write_text(
        yaml.dump({
            "files": ["harness/hooks/context_scope.py"],
            "delta": ["EDIT harness/hooks/context_scope.py"],
        }),
        encoding="utf-8",
    )

    adapter = BashPolicyAdapter()
    ctx_subagent = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "grep -rn 'foo' unlisted_dir/"},
        cwd=workspace,
        session_id="test-sess-search-subagent",
        raw_payload={
            "tool_name": "Bash",
            "tool_input": {"command": "grep -rn 'foo' unlisted_dir/"},
            "cwd": str(workspace),
            "session_id": "test-sess-search-subagent",
            "agent_type": "verify-implement",
        },
    )

    env = adapter.evaluate(ctx_subagent)
    assert env is not None, "Expected subagent search outside allowlist to be denied"
    assert env.is_deny
    assert "search_outside_scope_denied" in (env.reason or "")


def test_in_shard_search_allowed(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    """TM-I2-078-04: In-shard search targets within allowlist are allowed without graphify."""
    monkeypatch.delenv("EPIC_LOOP", raising=False)

    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    target_file = workspace / "src" / "module.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("def run(): pass\n", encoding="utf-8")

    step_dir = mb_dir / "back" / "plan" / "T-HUB-100" / "yaml" / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    shard_path = step_dir / "s01.yaml"
    shard_path.write_text(
        yaml.dump({
            "files": ["src/module.py"],
            "delta": ["EDIT src/module.py"],
        }),
        encoding="utf-8",
    )

    adapter = BashPolicyAdapter()
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "rg 'def run' src/module.py"},
        cwd=workspace,
        session_id="test-sess-in-scope",
    )

    env = adapter.evaluate(ctx)
    assert env is None or not env.is_deny


def test_bash_pretool_test_command_detected(workspace: Path):
    """FR-002 / cp1 (s03): BashPolicyAdapter detects normalized test commands and queries TestFingerprintCache."""
    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    cache = TestFingerprintCache(project_root=workspace)
    cache.record("bin/pytest harness/hooks/tests/test_foo.py", exit_code=0, output_summary="1 passed")

    adapter = BashPolicyAdapter()
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "bin/pytest harness/hooks/tests/test_foo.py"},
        cwd=workspace,
        session_id="sess-test-cmd",
    )
    env = adapter.evaluate(ctx)
    assert env is not None, "Expected test command detection in BashPolicyAdapter"


def test_bash_pretool_test_cache_hit(workspace: Path):
    """TM-I2-078-01 / FR-002: Repeat test cmd unchanged -> cache hit -> cached decision envelope with DecisionReceipt."""
    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\\n", encoding="utf-8")

    test_file = workspace / "tests" / "test_sample.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")

    cmd = f"bin/pytest {test_file.relative_to(workspace)}"
    cache = TestFingerprintCache(project_root=workspace)
    cache.record(cmd, exit_code=0, output_summary="1 passed", relevant_paths=[test_file])

    adapter = BashPolicyAdapter()
    ctx = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": cmd},
        cwd=workspace,
        session_id="sess-test-cache-hit",
    )
    env = adapter.evaluate(ctx)
    assert env is not None, "Expected cached execution envelope on repeated unchanged test command"
    assert "cached" in (env.reason or "").lower() or env.diagnostic_code == DiagnosticCode.RECORDED


test_bash_pretool_test_cache = test_bash_pretool_test_cache_hit


def test_edit_invalidates_test_cache_miss(workspace: Path):
    """TM-I2-078-02 / FR-002, FR-003: Edit relevant file -> cache invalidated -> subsequent test command misses."""
    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    src_file = workspace / "src" / "module.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("def fn(): return 1\n", encoding="utf-8")

    cmd = "bin/pytest tests/test_module.py"
    cache = TestFingerprintCache(project_root=workspace)
    cache.record(cmd, exit_code=0, output_summary="1 passed", relevant_paths=[src_file])

    # Invalidate path
    cache.invalidate_path(src_file)

    # Lookup in cache should now miss
    hit = cache.lookup(cmd, relevant_paths=[src_file])
    assert hit is None


def test_dot_directories_not_bypassed_without_allowlist(workspace: Path):
    """AC-2 / AC-6: .agents/, .claude/, .cursor/ directories are not unconditionally allowed outside allowlist."""
    shard_data = {
        "files": ["src/service.py"],
        "delta": ["EDIT src/service.py"],
    }
    resolver = ScopeResolver(project_root=workspace, shard_data=shard_data)

    # .cursor, .claude, .agents are outside shard allowlist
    assert not resolver.is_path_allowed(".cursor/rules/some_rule.mdc")
    assert not resolver.is_path_allowed(".claude/agents/worker.md")
    assert not resolver.is_path_allowed(".agents/skills/tdd/SKILL.md")

    # Search in these directories without graphify evidence is denied
    ok, reason, details = resolver.evaluate_search("rg 'foo' .cursor/")
    assert not ok
    assert reason == "search_outside_scope_denied"

    ok, reason, details = resolver.evaluate_search("rg 'foo' .agents/")
    assert not ok
    assert reason == "search_outside_scope_denied"


def test_compound_bash_commands_search_enforcement(workspace: Path):
    """BF-003 / AC-gap: compound Bash commands (cd && rg, env rg, bash -c, pipes) enforce search scope."""
    shard_data = {
        "files": ["src/service.py"],
        "delta": ["EDIT src/service.py"],
    }
    resolver = ScopeResolver(project_root=workspace, shard_data=shard_data)

    # 1. cd .agents && rg foo -> denied
    cmd1 = "cd .agents && rg foo"
    assert is_search_command_line(cmd1)
    ok1, reason1, details1 = resolver.evaluate_search(cmd1)
    assert not ok1
    assert reason1 == "search_outside_scope_denied"

    # 2. env rg foo -> denied (defaults to entire repo .)
    cmd2 = "env rg foo"
    assert is_search_command_line(cmd2)
    ok2, reason2, details2 = resolver.evaluate_search(cmd2)
    assert not ok2
    assert reason2 == "search_outside_scope_denied"

    # 3. env rg foo src/service.py -> allowed
    cmd3 = "env rg foo src/service.py"
    assert is_search_command_line(cmd3)
    ok3, reason3, details3 = resolver.evaluate_search(cmd3)
    assert ok3
    assert reason3 == "search_inside_scope"

    # 4. bash -c "cd .agents && rg foo" -> denied
    cmd4 = 'bash -c "cd .agents && rg foo"'
    assert is_search_command_line(cmd4)
    ok4, reason4, details4 = resolver.evaluate_search(cmd4)
    assert not ok4
    assert reason4 == "search_outside_scope_denied"

    # 5. bash -c "rg foo src/service.py" -> allowed
    cmd5 = 'bash -c "rg foo src/service.py"'
    assert is_search_command_line(cmd5)
    ok5, reason5, details5 = resolver.evaluate_search(cmd5)
    assert ok5
    assert reason5 == "search_inside_scope"

    # 6. cat .agents/SKILL.md | grep foo -> denied (.agents out of scope)
    cmd6 = "cat .agents/SKILL.md | grep foo"
    assert is_search_command_line(cmd6)
    ok6, reason6, details6 = resolver.evaluate_search(cmd6)
    assert not ok6
    assert reason6 == "search_outside_scope_denied"

    # 7. cat src/service.py | grep foo -> allowed (file in scope, grep reads stdin)
    cmd7 = "cat src/service.py | grep foo"
    assert is_search_command_line(cmd7)
    ok7, reason7, details7 = resolver.evaluate_search(cmd7)
    assert ok7
    assert reason7 == "search_inside_scope"

    # 8. VAR=1 BAR=2 rg foo -> denied
    cmd8 = "VAR=1 BAR=2 rg foo"
    assert is_search_command_line(cmd8)
    ok8, reason8, details8 = resolver.evaluate_search(cmd8)
    assert not ok8
    assert reason8 == "search_outside_scope_denied"

    # 9. (cd .agents && rg foo) -> denied
    cmd9 = "(cd .agents && rg foo)"
    assert is_search_command_line(cmd9)
    ok9, reason9, details9 = resolver.evaluate_search(cmd9)
    assert not ok9
    assert reason9 == "search_outside_scope_denied"

    # 10. echo hi; rg foo .cursor/ -> denied
    cmd10 = "echo hi; rg foo .cursor/"
    assert is_search_command_line(cmd10)
    ok10, reason10, details10 = resolver.evaluate_search(cmd10)
    assert not ok10
    assert reason10 == "search_outside_scope_denied"


def test_bash_pretool_compound_search_denied_and_allowed(workspace: Path):
    """BF-003: BashPolicyAdapter denies compound out-of-scope search and allows in-scope search."""
    mb_dir = workspace / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "activeContext.md").write_text("---\nepic_id: T-HUB-100\nstep_id: s01\n---\n", encoding="utf-8")

    target_file = workspace / "src" / "module.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("def run(): pass\n", encoding="utf-8")

    step_dir = mb_dir / "back" / "plan" / "T-HUB-100" / "yaml" / "steps"
    step_dir.mkdir(parents=True, exist_ok=True)
    shard_path = step_dir / "s01.yaml"
    shard_path.write_text(
        yaml.dump({
            "files": ["src/module.py"],
            "delta": ["EDIT src/module.py"],
        }),
        encoding="utf-8",
    )

    adapter = BashPolicyAdapter()

    # 1. Compound search outside scope -> DENY
    ctx_deny = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "cd .agents && rg 'def run'"},
        cwd=workspace,
        session_id="test-sess-compound-deny",
    )
    env_deny = adapter.evaluate(ctx_deny)
    assert env_deny is not None and env_deny.is_deny
    assert "search_outside_scope_denied" in env_deny.reason

    # 2. Compound search wrapped with env inside scope -> ALLOW
    ctx_allow = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "env rg 'def run' src/module.py"},
        cwd=workspace,
        session_id="test-sess-compound-allow",
    )
    env_allow = adapter.evaluate(ctx_allow)
    assert env_allow is None or not env_allow.is_deny

    # 3. bash -c compound search outside scope -> DENY
    ctx_bash_c = EventContext(
        event_name=PreToolUse,
        tool_name="Bash",
        tool_input={"command": "bash -c \"cd .agents && rg foo\""},
        cwd=workspace,
        session_id="test-sess-bash-c-deny",
    )
    env_bash_c = adapter.evaluate(ctx_bash_c)
    assert env_bash_c is not None and env_bash_c.is_deny
    assert "search_outside_scope_denied" in env_bash_c.reason
