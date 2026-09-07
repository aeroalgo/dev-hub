"""Red tests for subagent-stop receipt emission and integrity verification.

Covers:
- CP2: Mutated receipts, digest mismatch, identity verification at subagent-stop boundary
- Verifier vs non-verifier identity checks
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import (
    current_gate_identity,
    match_gate_evidence,
    record_verdict,
    set_gate_identity,
    verdict_evidence,
)


def test_subagent_stop_receipt_mutation_detected():
    """FR-001, AC+2, TM-077-02: Receipt tampering detected when field changed after hash."""
    identity = {
        "session_id": "session-1",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    evidence = verdict_evidence(identity, "PASS")
    # Mutating an essential field in evidence
    evidence["step"] = "s02"
    matched, diagnostic = match_gate_evidence(evidence, identity)
    assert matched is False
    assert diagnostic in ("verdict_stale", "verdict_wrong_step", "receipt_identity_mismatch", "receipt_digest_mismatch")


def test_subagent_stop_epoch_or_session_mismatch_detected():
    """FR-001, FR-002, TM-077-04: Old epoch in evidence rejected."""
    current_identity = {
        "session_id": "session-2",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-2",
        "phase_epoch": "epoch-2",
        "event_digest": "digest-2",
        "authority": "autonomous",
    }
    old_evidence = verdict_evidence(
        {
            **current_identity,
            "phase_epoch": "epoch-1",
            "projection_hash": "hash-1",
        },
        "PASS",
    )
    matched, diagnostic = match_gate_evidence(old_evidence, current_identity)
    assert matched is False
    assert diagnostic in ("verdict_stale", "epoch_mismatch", "receipt_stale")


def test_subagent_stop_receipt_emitter_and_mirror():
    """FR-001, CP2: Only subagent-stop accepted verifier/reviewer completion emits a valid receipt."""
    from gate_receipt import validate_verifier_receipt
    identity = {
        "session_id": "session-test",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s02",
        "projection_hash": "hash-test",
        "phase_epoch": "epoch-test",
        "event_digest": "digest-test",
        "authority": "autonomous",
    }
    receipt = verdict_evidence(identity, "PASS", verifier_identity="verify-implement")
    valid, diag = validate_verifier_receipt(receipt, identity)
    assert valid is True
    assert diag == "matched"
    assert receipt["schema"] == "loop-verifier-receipt/v1"
    assert receipt["receipt_digest"].startswith("sha256:")

    # manual authority evidence is rejected
    manual_receipt = dict(receipt, authority="manual")
    valid_manual, diag_manual = validate_verifier_receipt(manual_receipt, identity)
    assert valid_manual is False
    assert diag_manual == "manual_authority_rejected"

