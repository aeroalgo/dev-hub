"""Unit tests for phase-runner TodoWrite lifecycle policy and limit enforcement."""

import json
from typing import Any
import pytest

from harness.hooks.session_resilience import _todowrite_policy_summary
from loop.context_loop import (
    TodoPolicyDecision,
    TodoWritePolicy,
    enforce_phase_todowrite_policy,
    evaluate_todowrite_request,
    handle_todowrite_request,
)
from loop.lifecycle import TodoLifecycleManager
from loop.runtime.session_events import SessionEvent


def test_todowrite_lifecycle_max_events():
    """cp2: Phase runner permits at most start+finish events for IMPLEMENT; third request is rejected without side effects."""
    assert TodoWritePolicy is TodoLifecycleManager
    policy = TodoWritePolicy(phase="IMPLEMENT", max_allowed=2)
    assert policy.is_request_allowed() is True

    # 1. First request: start event (allowed, side_effect=True)
    first = policy.record_todowrite_request(payload={"action": "plan", "items": ["task 1"]})
    assert isinstance(first, TodoPolicyDecision)
    assert first.allowed is True
    assert first.action == "start"
    assert first.call_count == 1
    assert first.diagnostic is None
    assert first.side_effect is True
    assert policy.is_request_allowed() is True

    # 2. Second request: finish event (allowed, side_effect=True)
    second = policy.record_todowrite_request(payload={"action": "done", "items": ["task 1 complete"]})
    assert isinstance(second, TodoPolicyDecision)
    assert second.allowed is True
    assert second.action == "finish"
    assert second.call_count == 2
    assert second.diagnostic is None
    assert second.side_effect is True
    assert policy.is_request_allowed() is False

    # 3. Third request: rejected deterministically without side effects
    third = policy.record_todowrite_request(payload={"action": "update", "items": ["extra update"]})
    assert isinstance(third, TodoPolicyDecision)
    assert third.allowed is False
    assert third.action == "rejected"
    assert third.call_count == 3
    assert third.diagnostic == "todowrite_limit_exceeded"
    assert third.side_effect is False
    assert policy.is_request_allowed() is False

    # 4. Fourth request: also rejected deterministically
    fourth = policy.record_todowrite_request(payload={"action": "extra"})
    assert fourth.allowed is False
    assert fourth.action == "rejected"
    assert fourth.call_count == 4
    assert fourth.diagnostic == "todowrite_limit_exceeded"
    assert fourth.side_effect is False

    # Telemetry and history contains all 4 recorded requests
    assert len(policy.history) == 4
    assert policy.history[0].allowed is True
    assert policy.history[1].allowed is True
    assert policy.history[2].allowed is False
    assert policy.history[3].allowed is False


def test_evaluate_todowrite_request_pure():
    """Verify stateless evaluate_todowrite_request function."""
    d1 = evaluate_todowrite_request("IMPLEMENT", 1)
    assert d1.allowed is True
    assert d1.action == "start"
    assert d1.side_effect is True

    d2 = evaluate_todowrite_request("IMPLEMENT", 2)
    assert d2.allowed is True
    assert d2.action == "finish"
    assert d2.side_effect is True

    d3 = evaluate_todowrite_request("IMPLEMENT", 3)
    assert d3.allowed is False
    assert d3.action == "rejected"
    assert d3.side_effect is False
    assert d3.diagnostic == "todowrite_limit_exceeded"

    # Non-IMPLEMENT phase (e.g. PLAN) is not rejected at count 3
    d_plan = evaluate_todowrite_request("PLAN", 3)
    assert d_plan.allowed is True
    assert d_plan.side_effect is True


def test_enforce_phase_todowrite_policy_runner():
    """Verify phase runner enforcement helper on request batch."""
    requests = [
        {"action": "plan"},
        {"action": "finish"},
        {"action": "extra"},
        {"action": "another"},
    ]
    decisions = enforce_phase_todowrite_policy("IMPLEMENT", requests, max_allowed=2)
    assert len(decisions) == 4
    assert decisions[0].allowed is True
    assert decisions[0].action == "start"
    assert decisions[0].side_effect is True

    assert decisions[1].allowed is True
    assert decisions[1].action == "finish"
    assert decisions[1].side_effect is True

    assert decisions[2].allowed is False
    assert decisions[2].action == "rejected"
    assert decisions[2].side_effect is False
    assert decisions[2].diagnostic == "todowrite_limit_exceeded"

    assert decisions[3].allowed is False
    assert decisions[3].action == "rejected"
    assert decisions[3].side_effect is False


def test_enforce_phase_todowrite_policy_uses_existing_interceptor_policy():
    policy = TodoWritePolicy(phase="IMPLEMENT", max_allowed=2)
    side_effects: list[Any] = []

    decisions = enforce_phase_todowrite_policy(
        "IMPLEMENT",
        [{"action": "start"}, {"action": "finish"}, {"action": "extra"}],
        policy=policy,
        apply=side_effects.append,
    )

    assert [decision.call_count for decision in decisions] == [1, 2, 3]
    assert [decision.allowed for decision in decisions] == [True, True, False]
    assert side_effects == [{"action": "start"}, {"action": "finish"}]
    assert policy.call_count == 3


def test_handle_todowrite_request_hook():
    """Verify handle_todowrite_request hook runs side-effect on allowed and skips on rejected."""
    policy = TodoWritePolicy(phase="IMPLEMENT", max_allowed=2)
    side_effects: list[Any] = []

    def apply_effect(payload: Any) -> None:
        side_effects.append(payload)

    # First request: allowed -> side effect runs
    d1 = handle_todowrite_request(policy, {"action": "start"}, apply=apply_effect)
    assert d1.allowed is True
    assert d1.side_effect is True
    assert len(side_effects) == 1
    assert side_effects[0] == {"action": "start"}

    # Second request: allowed -> side effect runs
    d2 = handle_todowrite_request(policy, {"action": "finish"}, apply=apply_effect)
    assert d2.allowed is True
    assert d2.side_effect is True
    assert len(side_effects) == 2
    assert side_effects[1] == {"action": "finish"}

    # Third request: rejected -> side effect does NOT run
    d3 = handle_todowrite_request(policy, {"action": "extra"}, apply=apply_effect)
    assert d3.allowed is False
    assert d3.side_effect is False
    assert d3.diagnostic == "todowrite_limit_exceeded"
    assert len(side_effects) == 2  # Unchanged!


def test_session_resilience_todowrite_summary_parses_raw_requests():
    raw_log = "\n".join(
        json.dumps(
            {"type": "tool_use", "name": tool_name, input_key: {"action": action}}
        )
        for tool_name, input_key, action in (
            ("TodoWrite", "input", "start"),
            ("todo_write", "arguments", "finish"),
            ("todo-write", "params", "extra"),
        )
    )

    summary = _todowrite_policy_summary([], raw_log, phase="IMPLEMENT")

    assert summary["todowrite_phase"] == "IMPLEMENT"
    assert summary["todowrite_max_allowed"] == 2
    assert [event["sequence"] for event in summary["todowrite_events"]] == [0, 1, 2]
    assert [decision["action"] for decision in summary["todowrite_decisions"]] == [
        "start",
        "finish",
        "rejected",
    ]
    assert summary["todowrite_decisions"][2]["side_effect"] is False
    assert summary["todowrite_policy_violations"] == ["todowrite_limit_exceeded"]


def test_session_resilience_todowrite_summary_uses_structured_events():
    events = [
        SessionEvent(
            runtime="claude",
            event_type="tool_start",
            sequence=4,
            tool="TodoWrite",
            metadata={"action": "start"},
        ),
        SessionEvent(
            runtime="claude",
            event_type="tool_start",
            sequence=8,
            tool="todo_write",
            metadata={"action": "finish"},
        ),
    ]

    summary = _todowrite_policy_summary(events, "", phase="PLAN")

    assert [event["sequence"] for event in summary["todowrite_events"]] == [4, 8]
    assert [event["payload"] for event in summary["todowrite_events"]] == [
        {"action": "start"},
        {"action": "finish"},
    ]
    assert [decision["allowed"] for decision in summary["todowrite_decisions"]] == [
        True,
        True,
    ]
    assert summary["todowrite_policy_violations"] == []
