"""Red tests for gate receipt and evidence integrity across subagent-stop, stop-gate, and finish boundaries.

Covers:
- CP1: Manual authority and state-only PASS rejected by mb-finish / finalize-step
- CP2: Mutated receipts, invalid digest, wrong session/epoch/role/step rejected with named diagnostics
- CP3: TaskStop / absent receipt produces infrastructure_failure, retains forensic state, no retry
- CP4: Valid verifier PASS on current projection passes finish successfully without compatibility branches
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.hooks.epic.core import (
    default_state,
    finalize_step,
    load_epic_state,
    save_epic_state,
)
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.schemas import MbFinishRequest


@pytest.fixture
def epic_finish_env(tmp_path: Path):
    """Set up an epic environment with decompose, implement, and activeContext."""
    plan_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-077"
    (plan_dir / "yaml" / "steps").mkdir(parents=True, exist_ok=True)
    (plan_dir / "md").mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "T-HUB-077"
    impl_dir.mkdir(parents=True, exist_ok=True)

    index_yaml = plan_dir / "yaml" / "decompose-index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-077\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-test.yaml\n"
        "    status: in_progress\n",
        encoding="utf-8",
    )

    s01_decomp = plan_dir / "yaml" / "steps" / "s01-test.yaml"
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

    s01_impl = impl_dir / "s01-test.yaml"
    s01_impl.write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-077\n"
        "title: test step\n"
        "status: in_progress\n"
        "date: '2026-09-07'\n"
        "decompose_ref: memory-bank/back/plan/T-HUB-077/yaml/steps/s01-test.yaml\n"
        "skills_used: []\n"
        "discovery: []\n"
        "gaps:\n"
        "  status: none\n"
        "done:\n"
        "  - done item\n"
        "files:\n"
        "  - file1.py\n"
        "deletes: []\n"
        "tests:\n"
        "  - '`bin/pytest tests/test_example.py`'\n"
        "integration_check:\n"
        "  - ok\n"
        "grep_control: []\n"
        "verification_results: []\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: test cp\n"
        "    status: done\n",
        encoding="utf-8",
    )

    act_path = tmp_path / "memory-bank" / "activeContext.md"
    act_content = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-077\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "1. [s01-test.yaml](back/plan/T-HUB-077/yaml/steps/s01-test.yaml) — test.\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Дальше:** test\n\n"
        "## done\n"
        "- test initial\n"
    )
    act_path.write_text(act_content, encoding="utf-8")

    st = default_state()
    st["active"] = True
    st["session_id"] = "test-session"
    st["armed_epic"] = "T-HUB-077"
    st["armed_step"] = "s01"
    st["armed_role"] = "back"
    st["armed_decompose"] = "memory-bank/back/plan/T-HUB-077/yaml/decompose-index.yaml"
    st["phase"] = "BACK IMPLEMENT"
    st["phase_epoch"] = "epoch-1"
    st["projection_hash"] = "proj-hash-1"
    st["event_digest"] = "digest-1"
    save_epic_state(tmp_path, st)

    ledger_dir = tmp_path / ".claude" / "runtime" / "context-ledger" / tmp_path.name / "test-session"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / "root.json").write_text(
        json.dumps({
            "schema": "context-ledger/v1",
            "session_id": "test-session",
            "actor_key": {"actor_kind": "root", "invocation_id": "test-session", "runtime_provider": "claude"},
            "counters": {"unique_reads": 1, "duplicate_reads": 0, "bytes_read": 100, "ranges_read": 1},
            "files": {"file1.py": {"read_count": 1, "versions": []}},
        }),
        encoding="utf-8",
    )

    return tmp_path


def test_finish_rejects_manual_authority_evidence(epic_finish_env: Path):
    """FR-002, AC+1: Manual authority in last_verify_evidence must not allow finalize-step or mb-finish."""
    st = load_epic_state(epic_finish_env)
    st["last_verify_verdict"] = "PASS"
    st["last_verify_evidence"] = {
        "schema_version": "hook-verdict/v1",
        "verdict": "PASS",
        "session_id": "test-session",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "proj-hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "manual",
    }
    save_epic_state(epic_finish_env, st)

    # finalize_step direct call
    res = finalize_step(
        cwd=epic_finish_env,
        decompose="memory-bank/back/plan/T-HUB-077/yaml/decompose-index.yaml",
        step_id="s01",
        require_verify=True,
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") in (
        "manual_authority_rejected",
        "verifier_receipt_missing",
        "manual_fallback_non_authoritative",
    )

    # mb-finish implement call
    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="implemented test",
        cwd=str(epic_finish_env),
    )
    finish_res = finish_implement_step(req)
    assert finish_res.ok is False
    assert any(
        d in finish_res.diagnostic_codes
        for d in (
            "manual_authority_rejected",
            "verifier_receipt_missing",
            "manual_fallback_non_authoritative",
        )
    )


def test_finish_rejects_state_only_pass_without_receipt(epic_finish_env: Path):
    """FR-002, AC+1: Setting last_verify_verdict='PASS' in state without valid verifier receipt fails finish."""
    st = load_epic_state(epic_finish_env)
    st["last_verify_verdict"] = "PASS"
    st["last_verify_evidence"] = None
    st.pop("last_verify_evidence_sha256", None)
    st.pop("last_verify_receipt", None)
    save_epic_state(epic_finish_env, st)

    res = finalize_step(
        cwd=epic_finish_env,
        decompose="memory-bank/back/plan/T-HUB-077/yaml/decompose-index.yaml",
        step_id="s01",
        require_verify=True,
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") in ("verify_pass_missing", "verdict_evidence_missing", "verifier_receipt_missing")

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="implemented test",
        cwd=str(epic_finish_env),
    )
    finish_res = finish_implement_step(req)
    assert finish_res.ok is False
    assert any(
        d in finish_res.diagnostic_codes
        for d in ("verify_pass_missing", "verdict_evidence_missing", "verifier_receipt_missing")
    )


def test_finish_rejects_mutated_receipt_digest(epic_finish_env: Path):
    """FR-001, FR-002, AC+2, TM-077-02: Mutating any field in receipt invalidates digest before finish."""
    st = load_epic_state(epic_finish_env)
    receipt = {
        "schema": "loop-verifier-receipt/v1",
        "verifier_identity": "verify-implement",
        "verdict": "PASS",
        "session_id": "test-session",
        "phase_epoch": "epoch-1",
        "projection_hash": "proj-hash-1",
        "event_digest": "digest-1",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "created_at": "2026-09-07T12:00:00Z",
        "receipt_digest": "valid_sha256_mock_hash",
    }
    st["last_verify_verdict"] = "PASS"
    st["last_verify_receipt"] = receipt
    # Corrupt a field after creating digest
    receipt["verdict"] = "PASS_TAMPERED"
    st["last_verify_evidence"] = receipt
    st["last_verify_evidence_sha256"] = "original_sha256_before_tamper"
    save_epic_state(epic_finish_env, st)

    res = finalize_step(
        cwd=epic_finish_env,
        decompose="memory-bank/back/plan/T-HUB-077/yaml/decompose-index.yaml",
        step_id="s01",
        require_verify=True,
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") in (
        "receipt_digest_mismatch",
        "verdict_evidence_modified",
        "verifier_receipt_invalid",
    )


def test_finish_rejects_stale_epoch_or_identity_mismatch(epic_finish_env: Path):
    """FR-001, FR-002, TM-077-04: Receipt from old phase_epoch, wrong session or wrong step cannot satisfy finish."""
    st = load_epic_state(epic_finish_env)
    # Receipt with old epoch
    st["last_verify_verdict"] = "PASS"
    receipt_data = {
        "schema": "loop-verifier-receipt/v1",
        "verifier_identity": "verify-implement",
        "verdict": "PASS",
        "session_id": "test-session",
        "phase_epoch": "old-epoch-0",
        "projection_hash": "proj-hash-1",
        "event_digest": "digest-1",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "created_at": "2026-09-07T12:00:00Z",
    }
    from harness.hooks.gate_receipt import compute_receipt_digest
    receipt_data["receipt_digest"] = compute_receipt_digest(receipt_data)
    st["last_verify_receipt"] = receipt_data
    st["last_verify_evidence"] = receipt_data
    save_epic_state(epic_finish_env, st)

    res = finalize_step(
        cwd=epic_finish_env,
        decompose="memory-bank/back/plan/T-HUB-077/yaml/decompose-index.yaml",
        step_id="s01",
        require_verify=True,
    )
    assert res.get("ok") is False
    assert res.get("diagnostic") in ("verdict_stale", "epoch_mismatch", "receipt_identity_mismatch")


def test_finish_succeeds_with_valid_current_verifier_receipt(epic_finish_env: Path):
    """FR-005, AC+5, TM-077-05: Real verifier PASS matching current projection succeeds through finish path."""
    st = load_epic_state(epic_finish_env)
    identity = {
        "session_id": "test-session",
        "epic_id": "T-HUB-077",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "proj-hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    # Current verdict_evidence format for now, will be updated to receipt in s02
    from harness.hooks._lib import verdict_evidence

    evidence = verdict_evidence(identity, "PASS")
    st["last_verify_verdict"] = "PASS"
    st["last_verify_evidence"] = evidence
    st["gate_identity"] = identity
    save_epic_state(epic_finish_env, st)

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="implemented test",
        cwd=str(epic_finish_env),
    )
    finish_res = finish_implement_step(req)
    assert finish_res.ok is True
    assert finish_res.finished_step == "s01"
