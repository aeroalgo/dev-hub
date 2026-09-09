"""Unit tests for phase-runner TodoWrite lifecycle policy and limit enforcement."""

import pytest

from loop.context_loop import (
    TodoPolicyDecision,
    TodoWritePolicy,
    evaluate_todowrite_request,
)


def test_third_todowrite_rejected():
    """cp2: Phase runner permits at most start+finish events for IMPLEMENT; third request is rejected without side effects."""
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
