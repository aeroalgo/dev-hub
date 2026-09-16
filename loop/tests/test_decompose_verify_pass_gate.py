from __future__ import annotations

from pathlib import Path

from loop.decompose_gate import decompose_verify_pass_ready, phase_verify_pass_ready


def test_decompose_verify_pass_ready_rejects_fail() -> None:
    out = decompose_verify_pass_ready(
        Path("/tmp"),
        {"last_verify_verdict": "FAIL", "last_verify_evidence": {"agent_id": "verify-decompose"}},
    )
    assert out["ok"] is False
    assert out["diagnostic"] == "verify-decompose_pass_missing"


def test_decompose_verify_pass_ready_rejects_wrong_agent() -> None:
    out = decompose_verify_pass_ready(
        Path("/tmp"),
        {
            "last_verify_verdict": "PASS",
            "last_verify_evidence": {"agent_id": "verify-implement", "verdict": "PASS"},
        },
    )
    assert out["ok"] is False
    assert out["diagnostic"] == "verify-decompose_pass_missing"


def test_phase_verify_pass_ready_implement_requires_agent() -> None:
    out = phase_verify_pass_ready(
        Path("/tmp"),
        "IMPLEMENT",
        {
            "last_verify_verdict": "PASS",
            "last_verify_evidence": {"agent_id": "verify-decompose", "verdict": "PASS"},
        },
    )
    assert out["ok"] is False
    assert out["verify_agent"] == "verify-implement"


def test_phase_verify_pass_ready_plan_not_required() -> None:
    out = phase_verify_pass_ready(Path("/tmp"), "PLAN", {})
    assert out["ok"] is True
    assert out["diagnostic"] == "verify_not_required"


def test_decompose_verify_pass_ready_accepts_verify_decompose_without_evidence_match(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "epic.core.gate_evidence_matches",
        lambda cwd, evidence: (True, "ok"),
    )
    out = decompose_verify_pass_ready(
        Path("/tmp"),
        {
            "last_verify_verdict": "PASS",
            "last_verify_evidence": {
                "agent_id": "verify-decompose",
                "verdict": "PASS",
                "schema": "loop-gate-verdict/v1",
            },
        },
    )
    assert out["ok"] is True


def test_decompose_verify_accepts_receipt_when_projection_advanced_to_implement() -> None:
    """Premature IMPLEMENT projection must not block DECOMPOSE→ANALYZE arming."""
    from harness.hooks.gate_receipt import compute_receipt_digest, issue_verifier_receipt

    identity = {
        "session_id": "sess-decompose",
        "phase_epoch": "sha256:epoch-decompose",
        "projection_hash": "sha256:proj-decompose",
        "event_digest": "sha256:events-decompose",
        "epic_id": "T-HUB-106-dsh-runtime-full-purge",
        "role": "back",
        "step": "DECOMPOSE",
        "authority": "autonomous",
    }
    receipt = issue_verifier_receipt(identity, "PASS", "verify-decompose")
    assert receipt["receipt_digest"] == compute_receipt_digest(receipt)

    out = decompose_verify_pass_ready(
        Path("/tmp"),
        {
            "armed_epic": "T-HUB-106-dsh-runtime-full-purge",
            "armed_step": "s01",
            "phase": "BACK IMPLEMENT",
            "last_finished_step": "DECOMPOSE",
            "last_verify_verdict": "PASS",
            "last_verify_evidence": receipt,
            "projection": {
                "step": "s01",
                "next_step": "s01",
                "phase": "BACK IMPLEMENT",
                "projection_hash": "sha256:proj-implement",
                "phase_epoch": "sha256:epoch-implement",
                "event_digest": "sha256:events-implement",
            },
        },
    )
    assert out["ok"] is True
    assert out["diagnostic"] == "verify-decompose_pass"


def test_decompose_verify_rejects_receipt_bound_to_wrong_step() -> None:
    from harness.hooks.gate_receipt import issue_verifier_receipt

    identity = {
        "session_id": "sess-s01",
        "phase_epoch": "sha256:epoch",
        "projection_hash": "sha256:proj",
        "event_digest": "sha256:events",
        "epic_id": "T-HUB-106-dsh-runtime-full-purge",
        "role": "back",
        "step": "s01",
        "authority": "autonomous",
    }
    receipt = issue_verifier_receipt(identity, "PASS", "verify-decompose")
    out = decompose_verify_pass_ready(
        Path("/tmp"),
        {
            "armed_epic": "T-HUB-106-dsh-runtime-full-purge",
            "last_verify_verdict": "PASS",
            "last_verify_evidence": receipt,
        },
    )
    assert out["ok"] is False
    assert out["diagnostic"] == "verdict_wrong_step"
