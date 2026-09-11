#!/usr/bin/env python3
"""Unit tests for harness/hooks/gate_runtime.py shared pure services."""
from __future__ import annotations

import copy
import pytest
from typing import Any

from harness.hooks.gate_runtime import (
    BoundaryValidationResult,
    BoundaryValidator,
    EvidenceRecorder,
    EvidenceRecordResult,
    GateDiagnosticCode,
    IdentityService,
    SessionIdentity,
    VerdictExtractor,
    classify_retry_outcome,
)
from loop.gate_identity import (
    GATE_IDENTITY_SCHEMA,
    GateIdentity,
    GateOwnershipMismatchError,
)
from loop.schemas.boundary_registry import SCHEMA_LOOP_GATE_VERDICT, SCHEMA_LOOP_REPAIR_RESULT
from harness.hooks.gate_receipt import (
    RECEIPT_SCHEMA_VERSION,
    compute_receipt_digest,
    issue_verifier_receipt,
)


# ============================================================================
# Checkpoint 1 & TDD 1: Boundary Validator, JSON Fences, Schema & Ownership
# ============================================================================

def test_boundary_validation_fails_on_malformed_fence() -> None:
    """Malformed json fences return malformed_fence diagnostic code."""
    malformed_text = "Some report text\n```json\n{ invalid json content here: 123 \n```"
    fence, err = VerdictExtractor.extract_json_fence(malformed_text)
    assert fence is None
    assert err == GateDiagnosticCode.MALFORMED_FENCE

    verdict, payload, diag = VerdictExtractor.extract_verdict(malformed_text)
    assert verdict is None
    assert payload is None
    assert diag == GateDiagnosticCode.MALFORMED_FENCE


def test_boundary_validation_missing_or_mismatched_schema() -> None:
    """Missing or mismatched schema return typed diagnostic codes."""
    # Non-dict payload
    res1 = BoundaryValidator.validate_fence_and_schema(SCHEMA_LOOP_GATE_VERDICT, "not-a-dict")
    assert not res1.valid
    assert res1.diagnostic_code == GateDiagnosticCode.MISSING_SCHEMA

    # Dict without schema field
    res2 = BoundaryValidator.validate_fence_and_schema(
        SCHEMA_LOOP_GATE_VERDICT,
        {"agent_id": "verify-implement", "verdict": "PASS"},
    )
    assert not res2.valid
    assert res2.diagnostic_code == GateDiagnosticCode.MISSING_SCHEMA

    # Dict with wrong schema
    res3 = BoundaryValidator.validate_fence_and_schema(
        SCHEMA_LOOP_GATE_VERDICT,
        {"schema": "loop-wrong-schema/v1", "agent_id": "verify-implement", "verdict": "PASS"},
    )
    assert not res3.valid
    assert res3.diagnostic_code == GateDiagnosticCode.SCHEMA_MISMATCH


def test_boundary_validation_invalid_schema_fields() -> None:
    """Schema model validation failures return schema_invalid."""
    # Missing required fields for SCHEMA_LOOP_GATE_VERDICT
    payload = {
        "schema": SCHEMA_LOOP_GATE_VERDICT,
        "agent_id": "verify-implement",
        # missing step_id, session_id, epic_id, recorded_at, verdict
    }
    res = BoundaryValidator.validate_fence_and_schema(SCHEMA_LOOP_GATE_VERDICT, payload)
    assert not res.valid
    assert res.diagnostic_code == GateDiagnosticCode.SCHEMA_INVALID


def test_boundary_validation_ownership_mismatch() -> None:
    """Ownership mismatch (step_id or epic_id or session_id) returns ownership_mismatch."""
    valid_payload = {
        "schema": SCHEMA_LOOP_GATE_VERDICT,
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": "s02",
        "session_id": "sess-123",
        "epic_id": "T-HUB-085",
        "recorded_at": "2026-09-11T00:00:00Z",
    }
    expected_identity = SessionIdentity(
        session_id="sess-999",  # mismatched session
        epic_id="T-HUB-085",
        step_id="s02",
        role="back",
    )
    res = BoundaryValidator.validate_fence_and_schema(
        SCHEMA_LOOP_GATE_VERDICT,
        valid_payload,
        expected_identity=expected_identity,
        policy="strict",
    )
    assert not res.valid
    assert res.diagnostic_code == GateDiagnosticCode.OWNERSHIP_MISMATCH


def test_boundary_validation_valid_and_bound() -> None:
    """Valid payload passes schema and ownership validation."""
    valid_payload = {
        "schema": SCHEMA_LOOP_GATE_VERDICT,
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": "s02",
        "session_id": "sess-123",
        "epic_id": "T-HUB-085",
        "recorded_at": "2026-09-11T00:00:00Z",
    }
    expected_identity = SessionIdentity(
        session_id="sess-123",
        epic_id="T-HUB-085",
        step_id="s02",
        role="back",
    )
    res = BoundaryValidator.validate_fence_and_schema(
        SCHEMA_LOOP_GATE_VERDICT,
        valid_payload,
        expected_identity=expected_identity,
        agent_type="verify-implement",
        policy="strict",
    )
    assert res.valid
    assert res.diagnostic_code == GateDiagnosticCode.OK
    assert res.bound_payload is not None
    assert res.bound_payload["step_id"] == "s02"


# ============================================================================
# Checkpoint 2 & TDD 2 & 4: Identity Service & Anti-Forgery
# ============================================================================

def test_identity_matcher_rejects_stale_or_mismatched_session() -> None:
    """Identity matcher rejects mismatched step, epic, session or projection hash."""
    expected = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s02",
        projection_hash="hash-abc",
        phase_epoch=1,
    )

    # Stale step
    stale_step = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s01",  # stale
        projection_hash="hash-abc",
        phase_epoch=1,
    )
    ok, diag = IdentityService.validate_session_identity(stale_step, expected)
    assert not ok
    assert diag == GateDiagnosticCode.STALE_IDENTITY

    # Mismatched projection hash
    stale_hash = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s02",
        projection_hash="hash-xyz",  # mismatch
        phase_epoch=1,
    )
    ok, diag = IdentityService.validate_session_identity(stale_hash, expected)
    assert not ok
    assert diag == GateDiagnosticCode.STALE_IDENTITY


def test_manual_state_injection_rejected() -> None:
    """Manual state payload with authority='manual' is rejected fail-closed."""
    expected = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s02",
    )
    manual_claimed = {
        "session_id": "sess-001",
        "epic_id": "T-HUB-085",
        "step_id": "s02",
        "authority": "manual",
    }
    ok, diag = IdentityService.validate_session_identity(manual_claimed, expected)
    assert not ok
    assert diag == GateDiagnosticCode.MANUAL_STATE_REJECTED


def test_validate_receipt_proof_rejects_forged_digest_and_manual() -> None:
    """Receipt validation catches tampered/forged digest and manual receipts."""
    identity = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s02",
        role="back",
        phase_epoch=1,
        projection_hash="proj-hash-123",
        event_digest="evt-123",
        authority="autonomous",
    )
    valid_receipt = issue_verifier_receipt(identity.to_dict(), "PASS", "verify-implement")
    
    # Genuine receipt passes
    ok, diag = IdentityService.validate_receipt_proof(valid_receipt, identity)
    assert ok
    assert diag == GateDiagnosticCode.OK

    # Forged digest fails
    forged_receipt = copy.deepcopy(valid_receipt)
    forged_receipt["receipt_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    ok, diag = IdentityService.validate_receipt_proof(forged_receipt, identity)
    assert not ok
    assert diag == GateDiagnosticCode.FORGED_PAYLOAD

    # Manual authority receipt fails
    manual_receipt = copy.deepcopy(valid_receipt)
    manual_receipt["authority"] = "manual"
    manual_receipt["receipt_digest"] = compute_receipt_digest(manual_receipt)
    ok, diag = IdentityService.validate_receipt_proof(manual_receipt, identity)
    assert not ok
    assert diag == GateDiagnosticCode.MANUAL_STATE_REJECTED

    # Stale receipt (wrong step)
    stale_identity = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s03",  # different step
        role="back",
        phase_epoch=1,
        projection_hash="proj-hash-123",
        event_digest="evt-123",
    )
    ok, diag = IdentityService.validate_receipt_proof(valid_receipt, stale_identity)
    assert not ok
    assert diag == GateDiagnosticCode.STALE_IDENTITY


# ============================================================================
# Checkpoint 3 & TDD 3: Idempotent Evidence Recording
# ============================================================================

def test_evidence_recording_is_idempotent() -> None:
    """Evidence recording writes once and is idempotent across repeated calls."""
    state: dict[str, Any] = {}
    identity = SessionIdentity(
        session_id="sess-001",
        epic_id="T-HUB-085",
        step_id="s02",
        role="back",
        phase_epoch=1,
        projection_hash="proj-hash-1",
    )

    # First call: records new receipt
    res1 = EvidenceRecorder.record_gate_evidence(
        state,
        session_id="sess-001",
        tool_use_id="tool-use-100",
        agent_type="verify-implement",
        verdict="PASS",
        identity=identity,
    )
    assert res1.recorded
    assert res1.state_mutated
    assert res1.diagnostic_code == GateDiagnosticCode.RECORDED
    assert res1.receipt is not None
    assert state.get("last_gate_verdict") == "PASS"
    assert len(state.get("recorded_evidence_keys", [])) == 1

    # Second call with same parameters: idempotent skip
    res2 = EvidenceRecorder.record_gate_evidence(
        state,
        session_id="sess-001",
        tool_use_id="tool-use-100",
        agent_type="verify-implement",
        verdict="PASS",
        identity=identity,
    )
    assert res2.recorded
    assert not res2.state_mutated
    assert res2.diagnostic_code == GateDiagnosticCode.SKIPPED_DUPLICATE
    assert res2.dedupe_key == res1.dedupe_key
    assert len(state.get("recorded_evidence_keys", [])) == 1


def test_evidence_recording_rejects_invalid_verdict() -> None:
    """Evidence recorder rejects invalid verdict strings."""
    state: dict[str, Any] = {}
    identity = SessionIdentity(session_id="sess-001", epic_id="T-HUB-085", step_id="s02")
    res = EvidenceRecorder.record_gate_evidence(
        state,
        session_id="sess-001",
        tool_use_id="tool-1",
        agent_type="verify-implement",
        verdict="MAYBE",
        identity=identity,
    )
    assert not res.recorded
    assert res.diagnostic_code == GateDiagnosticCode.VERDICT_INVALID
    assert not res.state_mutated


# ============================================================================
# Checkpoint 4 & Extended: Retry Classification & Extraction
# ============================================================================

def test_classify_retry_outcome() -> None:
    """Schema issues are retryable under limit; ownership/identity failures are not."""
    # Schema issues: retryable if under max retries
    retryable, code = classify_retry_outcome(GateDiagnosticCode.SCHEMA_INVALID, schema_retry_count=0, max_retries=1)
    assert retryable
    assert code == GateDiagnosticCode.RETRYABLE

    exhausted, code = classify_retry_outcome(GateDiagnosticCode.SCHEMA_INVALID, schema_retry_count=1, max_retries=1)
    assert not exhausted
    assert code == "schema_retry_exhausted"

    # Malformed fence retryable
    retryable, code = classify_retry_outcome(GateDiagnosticCode.MALFORMED_FENCE, schema_retry_count=0)
    assert retryable

    # Non-retryable identity & forgery issues
    for diag in (
        GateDiagnosticCode.OWNERSHIP_MISMATCH,
        GateDiagnosticCode.STALE_IDENTITY,
        GateDiagnosticCode.FORGED_PAYLOAD,
        GateDiagnosticCode.MANUAL_STATE_REJECTED,
        GateDiagnosticCode.UNAUTHORIZED_VERIFIER,
    ):
        can_retry, code = classify_retry_outcome(diag, schema_retry_count=0)
        assert not can_retry
        assert code == GateDiagnosticCode.NON_RETRYABLE


def test_verdict_extractor_from_text_and_fence() -> None:
    """Extract verdict from both fence and text lines."""
    # From structured json fence
    fence_msg = (
        "Here is the report:\n```json\n"
        '{"schema": "loop-gate-verdict/v1", "agent_id": "verify-implement", "verdict": "PASS", '
        '"step_id": "s02", "session_id": "s1", "epic_id": "e1", "recorded_at": "2026-09-11T00:00:00Z"}\n'
        "```\nThank you."
    )
    v1, payload1, diag1 = VerdictExtractor.extract_verdict(fence_msg)
    assert v1 == "PASS"
    assert payload1 is not None
    assert diag1 is None

    # From text line
    text_msg = "All checks passed.\nVERDICT: FAIL\nSome blockers remain."
    v2, payload2, diag2 = VerdictExtractor.extract_verdict(text_msg)
    assert v2 == "FAIL"
    assert payload2 is None
    assert diag2 is None

    # Missing verdict
    empty_msg = "Nothing here."
    v3, payload3, diag3 = VerdictExtractor.extract_verdict(empty_msg)
    assert v3 is None
    assert diag3 == GateDiagnosticCode.VERDICT_MISSING
