"""Table-driven tests for harness/hooks/hook_dispatch.py dispatch abstractions."""
from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from harness.hooks.hook_dispatch import (
    DecisionEnvelope,
    DiagnosticCode,
    DispatchBranch,
    EventContext,
    LIFECYCLE_EVENTS,
    PostToolUse,
    PreToolUse,
    SessionStart,
    Stop,
    SubagentStart,
    SubagentStop,
    UserPromptSubmit,
    dispatch_event,
    dispatch_posttool,
    dispatch_pretool,
    dispatch_stop,
    dispatch_subagent_start,
    dispatch_subagent_stop,
    merge_updated_inputs,
    run_pipeline,
)


# ============================================================================
# Checkpoint 1: Ordered branch execution & first-deny short circuit
# ============================================================================

def test_branch_execution_order_sequence() -> None:
    """Verify that branches execute strictly in order: project boundary -> finish boundary -> tool policy."""
    execution_trace: list[str] = []

    def project_boundary_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("project_boundary")
        return DecisionEnvelope.allow()

    def finish_boundary_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("finish_boundary")
        return DecisionEnvelope.allow()

    def tool_policy_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("tool_policy")
        return DecisionEnvelope.allow(updated_input={"verified": True})

    branches = [
        DispatchBranch("project_boundary", project_boundary_branch),
        DispatchBranch("finish_boundary", finish_boundary_branch),
        DispatchBranch("tool_policy", tool_policy_branch),
    ]

    ctx = EventContext(event_name=PreToolUse, tool_name="Bash", tool_input={"command": "ls"})
    result = dispatch_pretool(ctx, branches)

    assert result.is_allow
    assert execution_trace == ["project_boundary", "finish_boundary", "tool_policy"]
    assert result.updated_input == {"verified": True}


def test_first_deny_halts_further_branch_checks() -> None:
    """Verify that the first deny branch stops execution immediately without invoking downstream checks."""
    execution_trace: list[str] = []

    def project_boundary_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("project_boundary")
        return DecisionEnvelope.deny("Project boundary violation", diagnostic_code=DiagnosticCode.PROJECT_BOUNDARY_DENY)

    def finish_boundary_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("finish_boundary")
        return DecisionEnvelope.allow()

    def tool_policy_branch(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("tool_policy")
        return DecisionEnvelope.allow()

    branches = [
        DispatchBranch("project_boundary", project_boundary_branch),
        DispatchBranch("finish_boundary", finish_boundary_branch),
        DispatchBranch("tool_policy", tool_policy_branch),
    ]

    ctx = EventContext(event_name=PreToolUse, tool_name="Write", tool_input={"file_path": "/etc/shadow"})
    result = dispatch_pretool(ctx, branches)

    assert result.is_deny
    assert result.reason == "Project boundary violation"
    assert result.diagnostic_code == DiagnosticCode.PROJECT_BOUNDARY_DENY
    assert execution_trace == ["project_boundary"]


def test_pretool_policy_sequence_project_finish_tool_first_deny() -> None:
    """Verify order and first deny at finish boundary stage."""
    execution_trace: list[str] = []

    def project_boundary(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("project_boundary")
        return None

    def finish_boundary(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("finish_boundary")
        return DecisionEnvelope.deny("Phase run already finished", diagnostic_code=DiagnosticCode.FINISH_BOUNDARY_DENY)

    def tool_policy(ctx: EventContext) -> DecisionEnvelope | None:
        execution_trace.append("tool_policy")
        return DecisionEnvelope.allow()

    branches = [
        DispatchBranch("project_boundary", project_boundary),
        DispatchBranch("finish_boundary", finish_boundary),
        DispatchBranch("tool_policy", tool_policy),
    ]

    ctx = EventContext(event_name=PreToolUse, tool_name="Read", tool_input={"file_path": "README.md"})
    result = dispatch_pretool(ctx, branches)

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.FINISH_BOUNDARY_DENY
    assert execution_trace == ["project_boundary", "finish_boundary"]


# ============================================================================
# Checkpoint 2: Conflicting updatedInput proposals & input merge logic
# ============================================================================

def test_merge_compatible_updated_input() -> None:
    """Non-conflicting updated inputs merge cleanly across branches."""
    b1 = {"param_a": 1, "nested": {"key1": "val1"}}
    b2 = {"param_b": 2, "nested": {"key2": "val2"}}

    merged, err = merge_updated_inputs(b1, b2)
    assert err is None
    assert merged == {
        "param_a": 1,
        "param_b": 2,
        "nested": {"key1": "val1", "key2": "val2"},
    }


def test_conflicting_updated_input_returns_conflict_diagnostic_without_partial_mutations() -> None:
    """Conflicting updatedInput proposals return structured conflict diagnostic without partial mutations."""
    initial_input = {"command": "bin/pytest", "timeout": 30}
    ctx = EventContext(event_name=PreToolUse, tool_name="Bash", tool_input=dict(initial_input))

    def branch_a(ctx: EventContext) -> DecisionEnvelope:
        return DecisionEnvelope.allow(updated_input={"timeout": 60, "env": {"FOO": "bar"}})

    def branch_b(ctx: EventContext) -> DecisionEnvelope:
        # Conflicting timeout proposed!
        return DecisionEnvelope.allow(updated_input={"timeout": 120, "extra": True})

    branches = [
        DispatchBranch("branch_a", branch_a),
        DispatchBranch("branch_b", branch_b),
    ]

    result = dispatch_pretool(ctx, branches)

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.CONFLICT_INPUT
    assert "Conflicting updatedInput" in (result.reason or "")
    assert result.diagnostic_details.get("branch") == "branch_b"
    assert result.updated_input is None


def test_deep_merge_conflict_rejection() -> None:
    """Nested structure conflicts are rejected with exact key path."""
    b1 = {"config": {"level": "debug", "opt": 1}}
    b2 = {"config": {"level": "info", "opt": 1}}

    merged, err = merge_updated_inputs(b1, b2)
    assert merged is None
    assert err is not None
    assert "config.level" in err


# ============================================================================
# Checkpoint 3: Fail-closed on unknown event/tool or unexpected exceptions
# ============================================================================

def test_unknown_event_fails_closed_with_diagnostic_code() -> None:
    """Unknown or malformed event fails closed with UNKNOWN_EVENT."""
    ctx = EventContext(event_name="InvalidLifecycleEvent", tool_name="Bash")
    result = dispatch_event(ctx, [])

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.UNKNOWN_EVENT
    assert "Unknown or unsupported lifecycle event" in (result.reason or "")


def test_unknown_tool_fails_closed_with_diagnostic_code() -> None:
    """Tool outside allowed set fails closed with UNKNOWN_TOOL."""
    ctx = EventContext(event_name=PreToolUse, tool_name="DangerousTool")
    result = dispatch_pretool(ctx, [], allowed_tools={"Bash", "Read", "Write"})

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.UNKNOWN_TOOL
    assert "DangerousTool" in (result.reason or "")


def test_unexpected_exception_fails_closed_with_diagnostic_code() -> None:
    """Unexpected exception inside branch fails closed with EXCEPTION diagnostic."""
    def crashing_branch(ctx: EventContext) -> DecisionEnvelope:
        raise RuntimeError("Disk read error or crash")

    branches = [DispatchBranch("crashing_branch", crashing_branch)]
    ctx = EventContext(event_name=PreToolUse, tool_name="Bash", tool_input={})
    result = dispatch_pretool(ctx, branches)

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.EXCEPTION
    assert "crashing_branch" in (result.reason or "")
    assert result.diagnostic_details.get("exception_type") == "RuntimeError"
    assert "Disk read error or crash" in result.diagnostic_details.get("exception_message", "")


def test_dispatch_exception_fails_closed_without_silent_allow() -> None:
    """FR-010 / TM-085-03: Exceptions in payload parsing / dispatch do not result in silent allow."""
    # Malformed payload that raises or returns invalid object
    def invalid_branch(ctx: EventContext) -> Any:
        return "not_a_decision_envelope"

    branches = [DispatchBranch("invalid_branch", invalid_branch)]
    ctx = EventContext(event_name=PreToolUse, tool_name="Bash")
    result = dispatch_pretool(ctx, branches)

    assert result.is_deny
    assert result.diagnostic_code == DiagnosticCode.SCHEMA_ERROR


# ============================================================================
# Checkpoint 4: Table-driven hook dispatch tests & lifecycle boundary parity
# ============================================================================

@pytest.mark.parametrize(
    "event_name,tool_name,payload,expected_decision,expected_diagnostic",
    [
        (PreToolUse, "Bash", {"command": "ls"}, "allow", DiagnosticCode.ALLOW),
        (PreToolUse, "Read", {"file_path": "harness/hooks/_lib.py"}, "allow", DiagnosticCode.ALLOW),
        (PostToolUse, "Bash", {"command": "ls", "output": "ok"}, "allow", DiagnosticCode.ALLOW),
        (SubagentStart, "", {"agent_type": "worker"}, "allow", DiagnosticCode.ALLOW),
        (SubagentStop, "", {"verdict": "PASS"}, "allow", DiagnosticCode.ALLOW),
        (Stop, "", {"phase_run_id": "run-1"}, "allow", DiagnosticCode.ALLOW),
        (SessionStart, "", {"session_id": "sess-1"}, "allow", DiagnosticCode.ALLOW),
        (UserPromptSubmit, "", {"prompt": "hello"}, "allow", DiagnosticCode.ALLOW),
    ],
)
def test_table_driven_lifecycle_events(
    event_name: str,
    tool_name: str,
    payload: dict[str, Any],
    expected_decision: str,
    expected_diagnostic: DiagnosticCode,
) -> None:
    """Table-driven tests covering canonical lifecycle events."""
    assert event_name in LIFECYCLE_EVENTS
    ctx = EventContext.from_payload(
        {"event_name": event_name, "tool_name": tool_name, "tool_input": payload}
    )
    assert ctx.event_name == event_name
    assert ctx.tool_name == tool_name

    def noop_branch(c: EventContext) -> DecisionEnvelope:
        return DecisionEnvelope.allow()

    result = dispatch_event(ctx, [DispatchBranch("noop", noop_branch)])
    assert result.decision == expected_decision
    assert result.diagnostic_code == expected_diagnostic


def test_subagent_boundaries_remain_distinct() -> None:
    """Prove that SubagentStart, SubagentStop, and Stop are distinct boundaries."""
    trace: list[str] = []

    def start_branch(c: EventContext) -> DecisionEnvelope:
        trace.append(SubagentStart)
        return DecisionEnvelope.allow()

    def stop_branch(c: EventContext) -> DecisionEnvelope:
        trace.append(SubagentStop)
        return DecisionEnvelope.allow()

    def final_stop_branch(c: EventContext) -> DecisionEnvelope:
        trace.append(Stop)
        return DecisionEnvelope.allow()

    # Distinct events dispatched separately
    r1 = dispatch_subagent_start({"agent_type": "verify"}, [DispatchBranch("start", start_branch)])
    r2 = dispatch_subagent_stop({"verdict": "PASS"}, [DispatchBranch("subagent_stop", stop_branch)])
    r3 = dispatch_stop({"phase_run_id": "123"}, [DispatchBranch("stop", final_stop_branch)])

    assert r1.is_allow
    assert r2.is_allow
    assert r3.is_allow
    assert trace == [SubagentStart, SubagentStop, Stop]


def test_hook_output_formatting_pretool_and_posttool() -> None:
    """Validate hookSpecificOutput formatting for Claude/Codex envelope compatibility."""
    # PreToolUse Allow with updatedInput
    allow_env = DecisionEnvelope.allow(
        updated_input={"timeout": 45},
        reason="Updated timeout policy",
    )
    pre_out = allow_env.to_hook_output(PreToolUse)
    assert pre_out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert pre_out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert pre_out["hookSpecificOutput"]["updatedInput"] == {"timeout": 45}
    assert pre_out["hookSpecificOutput"]["permissionReason"] == "Updated timeout policy"

    # PreToolUse Deny
    deny_env = DecisionEnvelope.deny("Write forbidden", diagnostic_code=DiagnosticCode.TOOL_POLICY_DENY)
    deny_out = deny_env.to_hook_output(PreToolUse)
    assert deny_out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert deny_out["hookSpecificOutput"]["permissionReason"] == "Write forbidden"
    assert deny_out["hookSpecificOutput"]["diagnosticCode"] == "tool_policy_deny"

    # PostToolUse
    post_env = DecisionEnvelope.record(reason="Evidence recorded", diagnostic_code=DiagnosticCode.RECORDED)
    post_out = post_env.to_hook_output(PostToolUse)
    assert post_out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert post_out["hookSpecificOutput"]["reason"] == "Evidence recorded"
    assert post_out["hookSpecificOutput"]["diagnosticCode"] == "recorded"
