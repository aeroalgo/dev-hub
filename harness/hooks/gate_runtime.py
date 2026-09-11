#!/usr/bin/env python3
"""Shared pure runtime services for gate identity, boundary validation, evidence and diagnostics.

This module provides normalized helper functions for:
- Session & Gate Identity matching and verification (SessionIdentity, GateIdentity)
- Boundary & JSON fence validation (BoundaryValidator)
- Verdict extraction from agent reports and structured messages (VerdictExtractor)
- Retry classification & diagnostic codes
- Idempotent evidence recording (EvidenceRecorder)
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop.gate_identity import (
    GATE_IDENTITY_SCHEMA,
    GateIdentity,
    GateOwnershipMismatchError,
    assert_fence,
    bind_fence,
)
from loop.schemas.boundary_registry import SCHEMA_LOOP_SUNSET_INVENTORY
from loop.validate_boundary import validate_boundary
from harness.hooks.gate_receipt import (
    ALLOWED_VERIFIER_IDENTITIES,
    RECEIPT_SCHEMA_VERSION,
    compute_receipt_digest,
    issue_verifier_receipt,
    validate_verifier_receipt,
)


# ============================================================================
# Diagnostics & Code Definitions
# ============================================================================

class GateDiagnosticCode:
    """Canonical diagnostic error & status codes."""
    OK = "ok"
    MALFORMED_FENCE = "malformed_fence"
    MISSING_SCHEMA = "missing_schema"
    SCHEMA_MISMATCH = "schema_mismatch"
    SCHEMA_INVALID = "schema_invalid"
    OWNERSHIP_MISMATCH = "ownership_mismatch"
    STALE_IDENTITY = "stale_identity"
    FORGED_PAYLOAD = "forged_payload"
    MANUAL_STATE_REJECTED = "manual_state_rejected"
    UNAUTHORIZED_VERIFIER = "unauthorized_verifier"
    VERDICT_MISSING = "verdict_missing"
    VERDICT_INVALID = "verdict_invalid"
    RECORDED = "recorded"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"


def _normalize_identity_dict(raw: Any) -> dict[str, Any]:
    """Normalize identity dictionary ensuring both step/step_id and epic/epic_id are present."""
    if isinstance(raw, (SessionIdentity, GateIdentity)):
        d = raw.to_dict()
    elif isinstance(raw, dict):
        d = dict(raw)
    else:
        return {}

    step = str(d.get("step_id") or d.get("step") or "").strip()
    epic = str(d.get("epic_id") or d.get("epic") or "").strip()
    if step:
        d["step"] = step
        d["step_id"] = step
    if epic:
        d["epic"] = epic
        d["epic_id"] = epic
    return d


@dataclass(frozen=True)
class SessionIdentity:
    """Normalized representation of a session and phase/step execution identity."""
    session_id: str = ""
    epic_id: str = ""
    step_id: str = ""
    role: str = ""
    phase: str = ""
    phase_epoch: Any = ""
    projection_hash: str = ""
    event_digest: str = ""
    authority: str = "autonomous"

    @property
    def step(self) -> str:
        return self.step_id

    @classmethod
    def from_mapping(cls, raw: Any) -> SessionIdentity:
        if not isinstance(raw, dict):
            return cls()
        step = str(raw.get("step_id") or raw.get("step") or "").strip()
        epic = str(raw.get("epic_id") or raw.get("epic") or "").strip()
        role = str(raw.get("role") or raw.get("armed_role") or "").strip()
        phase = str(raw.get("phase") or raw.get("loop_phase") or "").strip()
        session_id = str(raw.get("session_id") or "").strip()
        proj_hash = str(raw.get("projection_hash") or "").strip()
        phase_epoch = raw.get("phase_epoch") or ""
        authority = str(
            raw.get("authority")
            or ("autonomous" if proj_hash and phase_epoch else "manual")
        ).strip()
        return cls(
            session_id=session_id,
            epic_id=epic,
            step_id=step,
            role=role,
            phase=phase,
            phase_epoch=phase_epoch,
            projection_hash=proj_hash,
            event_digest=str(raw.get("event_digest") or "").strip(),
            authority=authority,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["step"] = self.step_id
        data["epic"] = self.epic_id
        return data

    def to_gate_identity(self) -> GateIdentity:
        return GateIdentity(
            schema=GATE_IDENTITY_SCHEMA,
            session_id=self.session_id,
            epic_id=self.epic_id,
            step_id=self.step_id,
            role=self.role,
            phase=self.phase,
            projection_hash=self.projection_hash,
            phase_epoch=self.phase_epoch,
            event_digest=self.event_digest,
            authority=self.authority,
        )


# ============================================================================
# Verdict Extractor
# ============================================================================

_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(\{.*?\})\n\s*```",
    re.DOTALL,
)

_VERDICT_LINE_RE = re.compile(
    r"(?im)^\s*(?:VERDICT|ИТОГ|РЕШЕНИЕ)\s*:\s*(PASS|FAIL|BLOCKED)\b"
)


class VerdictExtractor:
    """Pure extraction helper for JSON fences and text verdicts."""

    @staticmethod
    def extract_json_fence(text: str | None) -> tuple[dict[str, Any] | None, str | None]:
        """Extract first valid JSON fence from markdown-like text.
        
        Returns (parsed_dict, error_code). If valid, error_code is None.
        If no fence found, returns (None, None).
        If malformed JSON found, returns (None, GateDiagnosticCode.MALFORMED_FENCE).
        """
        if not text or not isinstance(text, str):
            return None, None
        
        # Look for code blocks
        matches = _JSON_FENCE_RE.findall(text)
        if not matches:
            # Check if there was an attempt at a json fence with invalid syntax
            if "```json" in text or "```" in text:
                raw_matches = re.findall(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
                for block in raw_matches:
                    block_s = block.strip()
                    if block_s.startswith("{") or block_s.endswith("}"):
                        try:
                            json.loads(block_s)
                        except Exception:
                            return None, GateDiagnosticCode.MALFORMED_FENCE
            return None, None

        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict):
                    return parsed, None
            except Exception:
                return None, GateDiagnosticCode.MALFORMED_FENCE
        return None, None

    @staticmethod
    def extract_text_verdict(text: str | None) -> str | None:
        """Extract line-based VERDICT: PASS|FAIL|BLOCKED."""
        if not text or not isinstance(text, str):
            return None
        match = _VERDICT_LINE_RE.search(text)
        if match:
            return match.group(1).upper()
        return None

    @classmethod
    def extract_verdict(
        cls,
        text: str | None,
        *,
        agent_type: str | None = None,
    ) -> tuple[str | None, dict[str, Any] | None, str | None]:
        """Extract verdict and structured payload from text.
        
        Returns (verdict, structured_data, diagnostic_code).
        """
        fence_data, fence_err = cls.extract_json_fence(text)
        if fence_err:
            return None, None, fence_err

        if isinstance(fence_data, dict):
            # Check if schema contains verdict
            v = fence_data.get("verdict")
            if v and isinstance(v, str):
                norm_v = v.strip().upper()
                if norm_v in {"PASS", "FAIL", "BLOCKED"}:
                    return norm_v, fence_data, None
                return None, fence_data, GateDiagnosticCode.VERDICT_INVALID

        # Fallback to text verdict line
        text_v = cls.extract_text_verdict(text)
        if text_v:
            return text_v, fence_data, None

        return None, fence_data, GateDiagnosticCode.VERDICT_MISSING


# ============================================================================
# Boundary Validator
# ============================================================================

@dataclass
class BoundaryValidationResult:
    valid: bool
    diagnostic_code: str
    diagnostics: list[str] = field(default_factory=list)
    bound_payload: dict[str, Any] | None = None


class BoundaryValidator:
    """Pure boundary & schema validation service."""

    @staticmethod
    def validate_fence_and_schema(
        expected_schema: str,
        payload: Any,
        expected_identity: SessionIdentity | GateIdentity | dict[str, Any] | None = None,
        *,
        agent_type: str | None = None,
        policy: str = "strict",
    ) -> BoundaryValidationResult:
        """Validate that payload matches schema and session/gate ownership."""
        if not isinstance(payload, dict):
            return BoundaryValidationResult(
                valid=False,
                diagnostic_code=GateDiagnosticCode.MISSING_SCHEMA,
                diagnostics=["Payload is not a valid JSON dictionary"],
            )

        schema = str(payload.get("schema") or "").strip()
        if not schema:
            return BoundaryValidationResult(
                valid=False,
                diagnostic_code=GateDiagnosticCode.MISSING_SCHEMA,
                diagnostics=["Payload is missing 'schema' attribute"],
            )

        if schema != expected_schema:
            return BoundaryValidationResult(
                valid=False,
                diagnostic_code=GateDiagnosticCode.SCHEMA_MISMATCH,
                diagnostics=[f"Schema mismatch: expected {expected_schema}, got {schema}"],
            )

        # Validate with boundary schema registry
        res = validate_boundary(expected_schema, payload)
        if not res.valid:
            return BoundaryValidationResult(
                valid=False,
                diagnostic_code=GateDiagnosticCode.SCHEMA_INVALID,
                diagnostics=res.diagnostic_codes or ["schema validation failed"],
            )

        # Validate identity / ownership if expected identity provided
        bound = copy.deepcopy(payload)
        if expected_identity is not None:
            # Convert SessionIdentity to GateIdentity for assert_fence / bind_fence
            exp_id_for_fence = (
                expected_identity.to_gate_identity()
                if isinstance(expected_identity, SessionIdentity)
                else expected_identity
            )
            try:
                if policy == "transport_bind":
                    bound = bind_fence(
                        bound,
                        exp_id_for_fence,
                        policy="transport_bind",
                        agent_type=agent_type,
                    )
                else:
                    assert_fence(
                        bound,
                        exp_id_for_fence,
                        policy="strict",
                        agent_type=agent_type,
                    )
            except GateOwnershipMismatchError as exc:
                return BoundaryValidationResult(
                    valid=False,
                    diagnostic_code=GateDiagnosticCode.OWNERSHIP_MISMATCH,
                    diagnostics=exc.mismatches or [str(exc)],
                    bound_payload=None,
                )
            except Exception as exc:
                return BoundaryValidationResult(
                    valid=False,
                    diagnostic_code=GateDiagnosticCode.OWNERSHIP_MISMATCH,
                    diagnostics=[str(exc)],
                    bound_payload=None,
                )

        return BoundaryValidationResult(
            valid=True,
            diagnostic_code=GateDiagnosticCode.OK,
            diagnostics=[],
            bound_payload=bound,
        )


# ============================================================================
# Identity Service
# ============================================================================

class IdentityService:
    """Pure identity validation and rejection service."""

    @staticmethod
    def validate_session_identity(
        claimed_identity: Any,
        expected_identity: SessionIdentity | GateIdentity | dict[str, Any],
    ) -> tuple[bool, str]:
        """Verify that claimed identity matches expected session identity."""
        if not isinstance(claimed_identity, (dict, SessionIdentity, GateIdentity)):
            return False, GateDiagnosticCode.STALE_IDENTITY

        claimed_dict = _normalize_identity_dict(claimed_identity)
        exp_dict = _normalize_identity_dict(expected_identity)

        # Check authority - reject manual injections as autonomous proof
        if claimed_dict.get("authority") == "manual":
            return False, GateDiagnosticCode.MANUAL_STATE_REJECTED

        # Key checks
        for key in ("session_id", "epic_id", "step_id", "step"):
            exp_v = exp_dict.get(key)
            if not exp_v:
                continue
            claim_v = claimed_dict.get(key)
            if claim_v and claim_v != exp_v:
                return False, GateDiagnosticCode.STALE_IDENTITY

        # Check epoch / projection hash if both present
        for key in ("projection_hash", "phase_epoch"):
            exp_v = exp_dict.get(key)
            claim_v = claimed_dict.get(key)
            if exp_v and claim_v and exp_v != claim_v:
                return False, GateDiagnosticCode.STALE_IDENTITY

        return True, GateDiagnosticCode.OK

    @staticmethod
    def validate_receipt_proof(
        receipt: Any,
        current_identity: SessionIdentity | GateIdentity | dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Validate that a verifier receipt is cryptographically sound and matches current identity."""
        if not isinstance(receipt, dict):
            return False, GateDiagnosticCode.FORGED_PAYLOAD

        cur_dict = _normalize_identity_dict(current_identity) if current_identity is not None else None

        valid, reason = validate_verifier_receipt(receipt, cur_dict)
        if not valid:
            if reason == "manual_authority_rejected":
                return False, GateDiagnosticCode.MANUAL_STATE_REJECTED
            if reason in {"receipt_digest_mismatch", "unauthorized_verifier_identity"}:
                return False, GateDiagnosticCode.FORGED_PAYLOAD
            if reason in {"verdict_stale", "verdict_wrong_step", "epoch_mismatch", "receipt_identity_missing", "projection_identity_missing"}:
                return False, GateDiagnosticCode.STALE_IDENTITY
            return False, GateDiagnosticCode.SCHEMA_INVALID

        return True, GateDiagnosticCode.OK


# ============================================================================
# Retry Classification
# ============================================================================

def classify_retry_outcome(
    diagnostic_code: str,
    *,
    schema_retry_count: int = 0,
    max_retries: int = 1,
) -> tuple[bool, str]:
    """Classify whether a failure is retryable or should be escalated to NEED_HUMAN.
    
    Returns (can_retry, reason).
    """
    if diagnostic_code in {
        GateDiagnosticCode.MALFORMED_FENCE,
        GateDiagnosticCode.MISSING_SCHEMA,
        GateDiagnosticCode.SCHEMA_MISMATCH,
        GateDiagnosticCode.SCHEMA_INVALID,
    }:
        if schema_retry_count < max_retries:
            return True, GateDiagnosticCode.RETRYABLE
        return False, "schema_retry_exhausted"

    if diagnostic_code in {
        GateDiagnosticCode.OWNERSHIP_MISMATCH,
        GateDiagnosticCode.STALE_IDENTITY,
        GateDiagnosticCode.FORGED_PAYLOAD,
        GateDiagnosticCode.MANUAL_STATE_REJECTED,
        GateDiagnosticCode.UNAUTHORIZED_VERIFIER,
    }:
        return False, GateDiagnosticCode.NON_RETRYABLE

    return False, GateDiagnosticCode.NON_RETRYABLE


# ============================================================================
# Idempotent Evidence Recorder
# ============================================================================

@dataclass
class EvidenceRecordResult:
    recorded: bool
    diagnostic_code: str
    dedupe_key: str
    receipt: dict[str, Any] | None = None
    state_mutated: bool = False


class EvidenceRecorder:
    """Idempotent evidence recording service for gate verdicts and verifier receipts."""

    @staticmethod
    def compute_idempotency_key(
        session_id: str,
        tool_use_id: str | None,
        agent_type: str,
        verdict: str,
    ) -> str:
        """Derive a stable deduplication/idempotency key."""
        raw = f"{session_id}:{tool_use_id or 'none'}:{agent_type}:{verdict.upper()}"
        return f"dedupe:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    @classmethod
    def record_gate_evidence(
        cls,
        state: dict[str, Any],
        *,
        session_id: str,
        tool_use_id: str | None,
        agent_type: str,
        verdict: str,
        identity: SessionIdentity | GateIdentity | dict[str, Any],
        report_text: str | None = None,
        diagnostic: str | None = None,
    ) -> EvidenceRecordResult:
        """Record verdict and receipt into state idempotently."""
        norm_verdict = str(verdict).upper().strip()
        if norm_verdict not in {"PASS", "FAIL", "BLOCKED"}:
            return EvidenceRecordResult(
                recorded=False,
                diagnostic_code=GateDiagnosticCode.VERDICT_INVALID,
                dedupe_key="",
            )

        dedupe_key = cls.compute_idempotency_key(session_id, tool_use_id, agent_type, norm_verdict)
        
        # Check if already recorded
        recorded_keys = state.setdefault("recorded_evidence_keys", [])
        if dedupe_key in recorded_keys:
            return EvidenceRecordResult(
                recorded=True,
                diagnostic_code=GateDiagnosticCode.SKIPPED_DUPLICATE,
                dedupe_key=dedupe_key,
                receipt=state.get("last_verifier_receipt"),
                state_mutated=False,
            )

        id_dict = _normalize_identity_dict(identity)
        receipt = issue_verifier_receipt(
            id_dict,
            norm_verdict,
            agent_type,
            diagnostic=diagnostic,
        )

        recorded_keys.append(dedupe_key)
        state["last_verifier_receipt"] = receipt
        state["last_gate_verdict"] = norm_verdict
        state["last_gate_agent"] = agent_type
        
        # Update gate identity in state
        state["gate_identity"] = id_dict

        return EvidenceRecordResult(
            recorded=True,
            diagnostic_code=GateDiagnosticCode.RECORDED,
            dedupe_key=dedupe_key,
            receipt=receipt,
            state_mutated=True,
        )
