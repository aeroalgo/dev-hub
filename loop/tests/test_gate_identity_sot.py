from __future__ import annotations

import pytest

from loop.gate_identity import (
    GATE_IDENTITY_SCHEMA,
    GateIdentity,
    GateOwnershipMismatchError,
    assert_fence,
    bind_fence,
    bind_spawn_gate,
    expected,
    freeze,
    inject_text,
)


def test_freeze_and_expected_ignore_armed() -> None:
    state = {
        "armed_epic": "T-HUB-091-gate-identity-sot-consolidation",
        "armed_step": "BUGFIX",
        "session_id": "sess-init-123",
        "role": "BACK",
        "phase": "BACK BUGFIX",
        "phase_run_id": "run-001",
    }
    frozen = GateIdentity.freeze(
        state,
        phase="BACK BUGFIX",
        step_id="BUGFIX",
        session_id="sess-init-123",
        phase_run_id="run-001",
    )
    assert state.get("session_start_identity") is not None
    assert state["session_start_identity"]["step_id"] == "BUGFIX"
    assert state["session_start_identity"]["epic_id"] == "T-HUB-091-gate-identity-sot-consolidation"
    assert frozen.step_id == "BUGFIX"
    assert frozen.step == "BUGFIX"

    # Simulate mid-session finish advancing armed_step and projection to QA
    state["armed_step"] = "QA"
    state["last_finished_step"] = "BUGFIX"
    state["armed_epic"] = "T-HUB-999-foreign-drift"
    state["projection"] = {
        "step": "QA",
        "epic_id": "T-HUB-999-foreign-drift",
        "projection_hash": "hash-abc",
        "phase_epoch": 2,
    }

    # expected(state) MUST ignore armed/projection drift and return frozen identity
    sot = GateIdentity.expected(state)
    assert sot.step_id == "BUGFIX"
    assert sot.step == "BUGFIX"
    assert sot.epic_id == "T-HUB-091-gate-identity-sot-consolidation"
    assert sot.session_id == "sess-init-123"
    assert sot.role == "BACK"
    assert sot.authority == "autonomous"

    # Test bind_spawn_gate mirror
    mirror = GateIdentity.bind_spawn_gate(state, sot)
    assert state["gate_identity"]["step"] == "BUGFIX"
    assert state["gate_identity"]["epic_id"] == "T-HUB-091-gate-identity-sot-consolidation"
    assert state["gate_identity"]["session_id"] == "sess-init-123"
    assert mirror["step"] == "BUGFIX"


def test_expected_fallback_without_freeze() -> None:
    state = {
        "armed_epic": "T-HUB-091",
        "armed_step": "s02",
        "session_id": "sess-fallback",
        "role": "BACK",
    }
    sot = GateIdentity.expected(state)
    assert sot.step_id == "s02"
    assert sot.epic_id == "T-HUB-091"
    assert sot.session_id == "sess-fallback"
    assert sot.authority == "manual"


def test_assert_and_bind_fence() -> None:
    exp = GateIdentity(
        session_id="sess-sot-1",
        epic_id="T-HUB-091",
        step_id="BUGFIX",
        role="BACK",
    )

    # 1. Strict assertion - success
    valid_fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "PASS",
        "step_id": "BUGFIX",
        "epic_id": "T-HUB-091",
        "session_id": "sess-sot-1",
    }
    assert GateIdentity.assert_fence(valid_fence, exp, policy="strict", agent_type="verify-bugfix") == []

    # 2. Strict assertion - step_id mismatch fails closed
    wrong_step_fence = dict(valid_fence, step_id="s05")
    with pytest.raises(GateOwnershipMismatchError) as exc_info:
        GateIdentity.assert_fence(wrong_step_fence, exp, policy="strict", agent_type="verify-bugfix")
    assert "step_id mismatch" in str(exc_info.value)
    assert any("step_id mismatch" in m for m in exc_info.value.mismatches)

    # 3. Strict assertion - epic_id mismatch fails closed
    wrong_epic_fence = dict(valid_fence, epic_id="T-HUB-FOREIGN")
    with pytest.raises(GateOwnershipMismatchError) as exc_info:
        GateIdentity.assert_fence(wrong_epic_fence, exp, policy="strict", agent_type="verify-bugfix")
    assert "epic_id mismatch" in str(exc_info.value)

    # 4. Strict assertion - session_id mismatch fails closed
    wrong_sess_fence = dict(valid_fence, session_id="wrong-sess")
    with pytest.raises(GateOwnershipMismatchError) as exc_info:
        GateIdentity.assert_fence(wrong_sess_fence, exp, policy="strict", agent_type="verify-bugfix")
    assert "session_id mismatch" in str(exc_info.value)

    # 5. Agent mismatch fails under strict
    wrong_agent_fence = dict(valid_fence, agent_id="reviewer")
    with pytest.raises(GateOwnershipMismatchError) as exc_info:
        GateIdentity.assert_fence(wrong_agent_fence, exp, policy="strict", agent_type="verify-bugfix")
    assert "agent_id mismatch" in str(exc_info.value)

    # 6. Transport bind - overwrites wrong step/epic/session with SoT
    foreign_fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-bugfix",
        "verdict": "FAIL",
        "step_id": "s05",
        "epic_id": "T-HUB-FOREIGN",
        "session_id": "foreign-sess",
    }
    bound = GateIdentity.bind_fence(foreign_fence, exp, policy="transport_bind", agent_type="verify-bugfix")
    assert bound["step_id"] == "BUGFIX"
    assert bound["epic_id"] == "T-HUB-091"
    assert bound["session_id"] == "sess-sot-1"

    # 7. Transport bind - agent mismatch STILL fails closed
    foreign_bad_agent = dict(foreign_fence, agent_id="verify-qa")
    with pytest.raises(GateOwnershipMismatchError) as exc_info:
        GateIdentity.bind_fence(foreign_bad_agent, exp, policy="transport_bind", agent_type="verify-bugfix")
    assert "agent_id mismatch" in str(exc_info.value)


def test_inject_text() -> None:
    sot = GateIdentity(
        session_id="sess-inject-789",
        epic_id="T-HUB-091-gate-identity-sot",
        step_id="s01",
    )
    text = GateIdentity.inject_text(sot)
    assert "GATE_IDENTITY session_id=sess-inject-789 epic_id=T-HUB-091-gate-identity-sot step_id=s01" in text
    assert "Fence MUST use these exact IDs for session_id, epic_id, and step_id." in text

    # Dict input test
    dict_input = {
        "session_id": "sess-dict-456",
        "epic_id": "T-HUB-DICT",
        "step": "s02",
    }
    dict_text = inject_text(dict_input)
    assert "GATE_IDENTITY session_id=sess-dict-456 epic_id=T-HUB-DICT step_id=s02" in dict_text


def test_gate_identity_mapping_and_dict_access() -> None:
    ident = GateIdentity(
        session_id="s1",
        epic_id="e1",
        step_id="step1",
        role="back",
    )
    assert ident["step"] == "step1"
    assert ident.get("step") == "step1"
    assert ident.get("epic_id") == "e1"
    assert ident.to_dict()["step"] == "step1"
    assert ident.to_dict()["step_id"] == "step1"

    # from_mapping
    mapped = GateIdentity.from_mapping({"session_id": "s2", "epic": "e2", "step": "step2"})
    assert mapped is not None
    assert mapped.session_id == "s2"
    assert mapped.epic_id == "e2"
    assert mapped.step_id == "step2"
    assert mapped.step == "step2"
