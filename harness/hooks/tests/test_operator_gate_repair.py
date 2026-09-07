"""Tests for audited operator repair command.

FR-005, AC+4, AC-2, TM-077-03, TM-077-05:
- Operator repair requires explicit authority and reason
- Operator repair records an immutable forensic audit event
- Operator repair can re-arm/clear stale in_flight/stuck states
- Operator repair CANNOT forge or mirror PASS (attempting to repair to PASS fails)
- Verifier receipt remains mandatory for finish success
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.hooks.epic.core import (
    default_state,
    finalize_step,
    load_epic_state,
    operator_repair_gate,
    save_epic_state,
)
from harness.hooks._lib import load_state, save_state
from harness.hooks.gate_receipt import issue_verifier_receipt


@pytest.fixture
def repair_env(tmp_path: Path):
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-077"
    mb_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-077"
    impl_dir.mkdir(parents=True, exist_ok=True)
    events_dir = tmp_path / "memory-bank" / "back" / "events" / "T-HUB-077"
    events_dir.mkdir(parents=True, exist_ok=True)

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-077\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-test.yaml\n"
        "    status: in_progress\n",
        encoding="utf-8",
    )

    s01_decomp = mb_dir / "s01-test.yaml"
    s01_decomp.write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-077\n"
        "title: test step\n"
        "next_phase: BACK IMPLEMENT\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: test cp\n",
        encoding="utf-8",
    )

    st = default_state()
    st["active"] = True
    st["session_id"] = "test-session"
    st["armed_epic"] = "T-HUB-077"
    st["armed_step"] = "s01"
    st["armed_role"] = "back"
    st["armed_decompose"] = "memory-bank/back/plan/decompose-T-HUB-077/index.yaml"
    st["phase"] = "BACK IMPLEMENT"
    st["phase_epoch"] = "epoch-1"
    st["projection_hash"] = "proj-hash-1"
    st["event_digest"] = "digest-1"
    st["in_flight"] = ["verify"]
    st["gate_diagnostic"] = "stale_in_flight"
    save_epic_state(tmp_path, st)

    spawn_st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "in_flight": ["verify"],
        "gate_diagnostic": "stale_in_flight",
    }
    save_state("test-session", str(tmp_path), spawn_st)

    return tmp_path


def test_operator_repair_requires_authority_and_reason(repair_env: Path):
    """Repair must fail without explicit operator authority and reason."""
    # Missing authority
    res = operator_repair_gate(
        cwd=repair_env,
        session_id="test-session",
        authority="",
        reason="fixing stale verify",
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") == "operator_authority_required"

    # Missing reason
    res = operator_repair_gate(
        cwd=repair_env,
        session_id="test-session",
        authority="operator",
        reason="",
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") == "repair_reason_required"


def test_operator_repair_prohibits_pass_injection(repair_env: Path):
    """Repair command cannot be used to forge or set PASS."""
    res = operator_repair_gate(
        cwd=repair_env,
        session_id="test-session",
        authority="operator",
        reason="attempting to bypass verifier",
        target_verdict="PASS",
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") == "repair_pass_prohibited"


def test_operator_repair_clears_stuck_state_and_records_forensic_event(repair_env: Path):
    """Audited operator repair re-arms the step and appends an immutable audit event."""
    res = operator_repair_gate(
        cwd=repair_env,
        session_id="test-session",
        authority="operator",
        reason="Reset stuck verify after crash",
        action="rearm",
    )
    assert res.get("ok") is True

    # State is re-armed
    st = load_epic_state(repair_env)
    assert "verify" not in st.get("in_flight", [])
    assert st.get("status") == "armed"

    spawn_st = load_state("test-session", str(repair_env))
    assert "verify" not in spawn_st.get("in_flight", [])

    # Audit event is recorded
    events_file = repair_env / "memory-bank" / "back" / "events" / "T-HUB-077" / "events.jsonl"
    assert events_file.is_file()
    lines = events_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    event = json.loads(lines[-1])
    assert event.get("kind") == "operator_repair"
    assert event.get("authority") == "operator"
    assert event.get("reason") == "Reset stuck verify after crash"
