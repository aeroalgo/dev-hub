"""Tests for finish_analyze and finish_audit (s07 / TM-008)."""

import sys
from pathlib import Path
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from harness.hooks._lib import current_gate_identity, verdict_evidence
from harness.hooks.epic.core import mirror_gate_verdict, read_active_context, save_epic_state
from loop.mb_finish.impl import (
    finish_analyze,
    finish_audit,
    finish_bugfix,
    finish_decompose,
    finish_plan,
    finish_qa,
)
from loop.mb_finish.schemas import MbFinishRequest, MbFinishResult


def test_finish_analyze_happy(tmp_path: Path):
    """cp1: finish_analyze happy path: gate evidence present → ok=True, mode=IMPLEMENT."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-TEST-001\nrole: back\nsteps: []\n",
        encoding="utf-8",
    )

    save_epic_state(
        tmp_path,
        {
            "active": True,
            "armed_epic": "T-TEST-001",
            "armed_role": "BACK",
            "armed_step": "ANALYZE",
            "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml",
            "session_id": "sess-test",
        },
    )

    identity = current_gate_identity(str(tmp_path), "sess-test")
    ev = verdict_evidence(identity, "PASS")
    ev["authority"] = "manual"
    mirror_gate_verdict(tmp_path, "PASS", evidence=ev)

    req = MbFinishRequest(
        phase="BACK ANALYZE",
        step_id="s07",
        done_summary="analyze complete",
        cwd=str(tmp_path),
    )

    res = finish_analyze(req)
    assert res.ok is True, f"Expected ok=True, got errors: {res.shape_errors} {res.diagnostic_codes}"
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: IMPLEMENT" in written


def test_finish_analyze_no_evidence(tmp_path: Path):
    """cp2: finish_analyze без gate evidence → ok=False, no phase advance."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-TEST-001",
            "armed_role": "BACK",
            "armed_step": "ANALYZE",
            "armed_decompose": "memory-bank/back/plan/decompose-T-TEST-001/index.yaml",
        },
    )

    req = MbFinishRequest(
        phase="BACK ANALYZE",
        step_id="s07",
        done_summary="analyze without evidence",
        cwd=str(tmp_path),
    )

    res = finish_analyze(req)
    assert res.ok is False
    assert "gate_evidence_missing" in res.diagnostic_codes


def test_finish_audit_happy(tmp_path: Path):
    """cp3: finish_audit happy path with valid audit artifact -> ok=True."""
    audit_dir = tmp_path / "memory-bank" / "back" / "audit" / "T-TEST-001"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "audit-001.yaml"
    audit_file.write_text("epic_id: T-TEST-001\nfindings: []\n", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-TEST-001",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK AUDIT",
        step_id="s07",
        done_summary="audit completed",
        cwd=str(tmp_path),
    )

    res = finish_audit(req)
    assert res.ok is True, f"Expected ok=True, got errors: {res.shape_errors} {res.diagnostic_codes}"
    assert res.active_context is not None

    written = read_active_context(tmp_path)
    assert "mode: QA" in written


def test_finish_audit_no_artifact(tmp_path: Path):
    """finish_audit without audit artifact returns ok=False."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    save_epic_state(tmp_path, {"armed_epic": "T-TEST-001", "armed_role": "BACK"})

    req = MbFinishRequest(
        phase="BACK AUDIT",
        step_id="s07",
        done_summary="audit missing",
        cwd=str(tmp_path),
    )

    res = finish_audit(req)
    assert res.ok is False
    assert "audit_artifact_missing" in res.diagnostic_codes


def test_finish_audit_invalid_artifact(tmp_path: Path):
    """finish_audit with empty or unreadable audit artifact returns ok=False."""
    audit_dir = tmp_path / "memory-bank" / "back" / "audit" / "T-TEST-001"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "audit-001.yaml"
    audit_file.write_text("   \n", encoding="utf-8")

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-TEST-001",
            "armed_role": "BACK",
        },
    )

    req = MbFinishRequest(
        phase="BACK AUDIT",
        step_id="s07",
        done_summary="audit empty",
        cwd=str(tmp_path),
    )

    res = finish_audit(req)
    assert res.ok is False
    assert "audit_artifact_invalid" in res.diagnostic_codes


@pytest.mark.parametrize(
    "fn",
    [
        finish_decompose,
        finish_plan,
        finish_analyze,
        finish_audit,
        finish_qa,
        finish_bugfix,
    ],
)
def test_uniform_contract_matrix(tmp_path: Path, fn):
    """cp4: matrix test: все phase tools возвращают MbFinishResult с полями ok + diagnostic_codes."""
    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)

    req = MbFinishRequest(
        phase="BACK TEST",
        step_id="s07",
        done_summary="test matrix",
        cwd=str(tmp_path),
    )

    res = fn(req)
    assert isinstance(res, MbFinishResult)
    assert isinstance(res.ok, bool)
    assert isinstance(res.diagnostic_codes, list)
    assert hasattr(res, "shape_errors")
    assert hasattr(res, "active_context")
