"""Tests for session identity resolution and PromptScope armed step contract (T-HUB-071)."""

import pytest
from loop.prompt_builder import build_prompt_scope, render_prompt_scope, PromptScope


def test_armed_qa_step_not_unknown_on_missing_projection_step(tmp_path):
    """US-002: Given armed_step=QA and projection.step missing, PromptScope.step must be 'QA', never 'unknown'."""
    # When state has armed_step='QA' or phase='QA', PromptScope must resolve step to 'QA', not 'unknown'
    projection = {"phase": "BACK QA", "role": "BACK", "epic": "T-HUB-071"}
    # Note: projection has no "step" or "next_step"
    scope = build_prompt_scope(
        tmp_path,
        projection=projection,
        fallback_command="BACK QA",
    )
    assert scope.step != "unknown", "scope.step must never be 'unknown' when armed in QA"
    assert scope.step == "QA", f"Expected step to be 'QA', got {scope.step!r}"


def test_armed_bugfix_step_not_unknown_when_step_omitted(tmp_path):
    """FR-008 / FR-013: When armed for BUGFIX, step must resolve to 'BUGFIX', not 'unknown'."""
    projection = {"phase": "BACK BUGFIX", "role": "BACK", "epic": "T-HUB-071"}
    scope = build_prompt_scope(
        tmp_path,
        projection=projection,
        fallback_command="BACK BUGFIX",
    )
    assert scope.step != "unknown"
    assert scope.step == "BUGFIX"


def test_armed_implement_with_step_snn(tmp_path):
    """US-004: IMPLEMENT phase with step=s03 resolves scope.step to 's03'."""
    projection = {"phase": "BACK IMPLEMENT", "role": "BACK", "step": "s03", "epic": "T-HUB-071"}
    scope = build_prompt_scope(
        tmp_path,
        projection=projection,
        fallback_command="BACK IMPLEMENT",
    )
    assert scope.step == "s03"
    assert scope.command == "BACK IMPLEMENT"


@pytest.mark.parametrize(
    "phase_token,expected_step,expected_command",
    [
        ("PLAN", "PLAN", "BACK PLAN"),
        ("DECOMPOSE", "DECOMPOSE", "BACK DECOMPOSE"),
        ("ANALYZE", "ANALYZE", "BACK ANALYZE"),
        ("CREATIVE", "CREATIVE", "BACK CREATIVE"),
        ("CLARIFY", "CLARIFY", "BACK CLARIFY"),
        ("AUDIT", "AUDIT", "BACK AUDIT"),
        ("QA", "QA", "BACK QA"),
        ("BUGFIX", "BUGFIX", "BACK BUGFIX"),
        ("DONE", "DONE", "DONE"),
    ],
)
def test_fr013_phase_matrix_tokens_and_commands(tmp_path, phase_token, expected_step, expected_command):
    """FR-013 / TM-008: All phase matrix tokens have non-unknown step token and correct COMMAND."""
    projection = {"phase": f"BACK {phase_token}", "role": "BACK", "epic": "T-HUB-071"}
    scope = build_prompt_scope(
        tmp_path,
        projection=projection,
        fallback_command=f"BACK {phase_token}",
    )
    assert scope.step != "unknown", f"Phase {phase_token} must not resolve to step='unknown'"
    assert scope.step == expected_step
    assert scope.command == expected_command


@pytest.mark.parametrize("step_token", ["s03", "s05", "e01"])
def test_armed_implement_step_snn_and_command(tmp_path, step_token):
    """US-004 / TM-004: IMPLEMENT + sNN gives step=sNN and COMMAND {ROLE} IMPLEMENT."""
    projection = {"phase": "BACK IMPLEMENT", "role": "BACK", "step": step_token, "epic": "T-HUB-071"}
    scope = build_prompt_scope(
        tmp_path,
        projection=projection,
        fallback_command="BACK IMPLEMENT",
    )
    assert scope.step == step_token
    assert scope.command == "BACK IMPLEMENT"
    assert scope.step != "unknown"


def test_failure_tm008_armed_implement_missing_snn_gives_diagnostic():
    """Failure-TM-008 / TM-008: Armed IMPLEMENT missing sNN produces step_unknown_while_armed drift, not unknown step."""
    from loop.prompt_builder import resolve_session_identity, Drift

    state = {"phase": "IMPLEMENT", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": ""}
    ac_meta = {"mode": "IMPLEMENT", "role": "BACK", "epic_id": "T-HUB-071", "step_id": ""}
    drift = resolve_session_identity(state, ac_meta)

    assert isinstance(drift, Drift)
    assert drift.code == "step_unknown_while_armed"
    assert drift.diagnostic_code == "CONTEXT_IDENTITY_DRIFT"


def test_unarmed_ide_tm005_documented_token_no_crash(tmp_path):
    """TM-005: Unarmed IDE does not crash, step resolves to '-' (documented non-unknown token)."""
    scope = build_prompt_scope(
        tmp_path,
        projection={},
        command=None,
        fallback_command=None,
    )
    assert scope.step == "-"
    assert scope.step != "unknown"
    assert scope.command == "UNKNOWN"
    rendered = render_prompt_scope(scope)
    assert "step: `-`" in rendered
    assert "COMMAND: UNKNOWN" in rendered


def test_epic_mismatch_tm006_halts():
    """TM-006: epic_id state vs AC mismatch produces epic_mismatch Drift halt."""
    from loop.prompt_builder import resolve_session_identity, Drift

    state = {"phase": "QA", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": "QA"}
    ac_meta = {"mode": "QA", "role": "BACK", "epic_id": "T-HUB-070"}
    drift = resolve_session_identity(state, ac_meta)

    assert isinstance(drift, Drift)
    assert drift.code == "epic_mismatch"
    assert drift.diagnostic_code == "CONTEXT_IDENTITY_DRIFT"


def test_resolve_session_identity_success():
    from loop.prompt_builder import resolve_session_identity, Identity

    state = {"phase": "QA", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": "QA"}
    ac_meta = {"mode": "QA", "role": "BACK", "epic_id": "T-HUB-071"}
    ident = resolve_session_identity(state, ac_meta)

    assert isinstance(ident, Identity)
    assert ident.role == "BACK"
    assert ident.phase == "QA"
    assert ident.step == "QA"
    assert ident.epic_id == "T-HUB-071"
    assert ident.command == "BACK QA"


def test_resolve_session_identity_phase_mismatch():
    from loop.prompt_builder import resolve_session_identity, Drift

    state = {"phase": "BUGFIX", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": "BUGFIX"}
    ac_meta = {"mode": "QA", "role": "BACK", "epic_id": "T-HUB-071"}
    drift = resolve_session_identity(state, ac_meta)

    assert isinstance(drift, Drift)
    assert drift.code == "phase_mismatch"
    assert drift.diagnostic_code == "CONTEXT_IDENTITY_DRIFT"
    assert drift.armed_step == "BUGFIX"
    assert drift.ac_mode == "QA"


def test_resolve_session_identity_epic_mismatch():
    from loop.prompt_builder import resolve_session_identity, Drift

    state = {"phase": "QA", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": "QA"}
    ac_meta = {"mode": "QA", "role": "BACK", "epic_id": "T-HUB-070"}
    drift = resolve_session_identity(state, ac_meta)

    assert isinstance(drift, Drift)
    assert drift.code == "epic_mismatch"
    assert drift.diagnostic_code == "CONTEXT_IDENTITY_DRIFT"


def test_resolve_session_identity_step_unknown_while_armed():
    from loop.prompt_builder import resolve_session_identity, Drift

    # Armed IMPLEMENT without sNN step
    state = {"phase": "IMPLEMENT", "role": "BACK", "epic_id": "T-HUB-071", "armed_step": ""}
    ac_meta = {"mode": "IMPLEMENT", "role": "BACK", "epic_id": "T-HUB-071", "step_id": ""}
    drift = resolve_session_identity(state, ac_meta)

    assert isinstance(drift, Drift)
    assert drift.code == "step_unknown_while_armed"


def test_unarmed_ide_step_is_dash(tmp_path):
    """FR-002: When nothing armed, step is '-' and not ambiguous 'unknown'."""
    scope = build_prompt_scope(
        tmp_path,
        projection={},
    )
    assert scope.step == "-"
    assert scope.step != "unknown"


