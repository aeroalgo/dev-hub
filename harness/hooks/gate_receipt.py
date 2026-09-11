"""Immutable gate verifier receipt schema, issuance, digest computation, and validation.

Schema: loop-verifier-receipt/v1
Immutable provenance:
- session_id
- phase_epoch
- projection_hash
- event_digest
- epic_id
- role
- step
- verifier_identity
- verdict
- created_at
- receipt_digest
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA_VERSION = "loop-verifier-receipt/v1"
ALLOWED_VERIFIER_IDENTITIES = frozenset(
    {"verify", "verify-implement", "verify-bugfix", "verify-decompose", "verify-qa", "reviewer", "analyze-verify"}
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_receipt_digest(payload: dict[str, Any]) -> str:
    """Compute deterministic canonical SHA256 digest over receipt provenance fields."""
    signed_fields = {
        "schema": payload.get("schema") or RECEIPT_SCHEMA_VERSION,
        "session_id": payload.get("session_id"),
        "phase_epoch": payload.get("phase_epoch"),
        "projection_hash": payload.get("projection_hash"),
        "event_digest": payload.get("event_digest"),
        "epic_id": payload.get("epic_id"),
        "role": payload.get("role"),
        "step": payload.get("step"),
        "verifier_identity": payload.get("verifier_identity"),
        "verdict": payload.get("verdict"),
        "created_at": payload.get("created_at"),
    }
    encoded = _canonical_json(signed_fields).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def issue_verifier_receipt(
    identity: dict[str, Any],
    verdict: str,
    verifier_identity: str,
    *,
    diagnostic: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Issue a new immutable verifier receipt with canonical digest."""
    norm_verdict = str(verdict).upper().strip()
    norm_verifier = str(verifier_identity).strip()
    ts = created_at or _utc_now_iso()

    payload = {
        "schema": RECEIPT_SCHEMA_VERSION,
        "session_id": identity.get("session_id"),
        "phase_epoch": identity.get("phase_epoch"),
        "projection_hash": identity.get("projection_hash"),
        "event_digest": identity.get("event_digest"),
        "epic_id": identity.get("epic_id"),
        "role": identity.get("role"),
        "step": identity.get("step"),
        "verifier_identity": norm_verifier,
        "verdict": norm_verdict,
        "created_at": ts,
        "authority": identity.get("authority", "autonomous"),
    }
    if diagnostic:
        payload["diagnostic"] = str(diagnostic)[:240]

    digest = compute_receipt_digest(payload)
    payload["receipt_digest"] = digest
    return payload


def validate_verifier_receipt(
    receipt: object,
    current_identity: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Validate receipt structure, digest integrity, and match with projection identity."""
    if not isinstance(receipt, dict):
        return False, "verifier_receipt_missing"

    schema = str(receipt.get("schema") or "").strip()
    if schema != RECEIPT_SCHEMA_VERSION:
        if receipt.get("authority") == "manual":
            return False, "manual_authority_rejected"
        return False, "verifier_receipt_invalid"

    if receipt.get("authority") == "manual":
        return False, "manual_authority_rejected"

    verifier_identity = str(receipt.get("verifier_identity") or "").strip()
    if not verifier_identity or (
        verifier_identity not in ALLOWED_VERIFIER_IDENTITIES
        and not any(verifier_identity.startswith(prefix) for prefix in ("verify", "reviewer"))
    ):
        return False, "unauthorized_verifier_identity"

    verdict = str(receipt.get("verdict") or "").upper().strip()
    if verdict not in {"PASS", "FAIL", "BLOCKED"}:
        return False, "verifier_receipt_invalid"

    claimed_digest = str(receipt.get("receipt_digest") or "").strip()
    if not claimed_digest:
        return False, "receipt_digest_mismatch"

    expected_digest = compute_receipt_digest(receipt)
    if claimed_digest != expected_digest:
        return False, "receipt_digest_mismatch"

    if current_identity is not None:
        required_keys = ("step", "projection_hash", "phase_epoch")
        for key in required_keys:
            if not receipt.get(key):
                return False, "receipt_identity_missing"
            if not current_identity.get(key):
                return False, "projection_identity_missing"

        for key in required_keys + ("epic_id", "role", "event_digest"):
            exp = current_identity.get(key)
            obs = receipt.get(key)
            if exp is not None and obs is not None:
                if key == "role":
                    if str(exp).strip().lower() != str(obs).strip().lower():
                        return False, "verdict_stale"
                    continue
                if obs != exp:
                    if key == "step":
                        return False, "verdict_wrong_step"
                    if key == "phase_epoch":
                        return False, "epoch_mismatch"
                    return False, "verdict_stale"

    return True, "matched"
