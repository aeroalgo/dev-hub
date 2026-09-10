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
