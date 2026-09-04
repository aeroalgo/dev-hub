"""Tests for finish_analyze and finish_audit (s07 / TM-008)."""

import json
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
    """cp1: finish_analyze happy path: analyze yaml + gate evidence → ok=True, mode=IMPLEMENT."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "back" / "plan").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "back" / "plan" / "plan-T-TEST-001.md").write_text(
        "# plan\n", encoding="utf-8"
    )

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "role: back\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-env.yaml\n"
        "  status: pending\n"
        "  next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )
    (mb_dir / "s01-env.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\nneeds_creative: 'no'\n",
        encoding="utf-8",
    )
    analyze_dir = tmp_path / "memory-bank" / "back" / "analyze" / "T-TEST-001"
    analyze_dir.mkdir(parents=True, exist_ok=True)
    (analyze_dir / "analyze-20260902-pass.yaml").write_text(
        "schema: epic-analyze/v1\n"
        "status: complete\n"
        "metrics:\n"
        "  critical_count: 0\n",
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
            "role": "BACK",
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


def test_finish_analyze_missing_artifact(tmp_path: Path):
    """finish_analyze without analyze yaml → ok=False, AC not advanced to IMPLEMENT."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (mb_dir / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-env.yaml\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    (mb_dir / "s01-env.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\n",
        encoding="utf-8",
    )
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: ANALYZE\n"
        "epic_id: T-TEST-001\nstep_id: ANALYZE\n---\n\n## load_now\n",
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
            "role": "BACK",
        },
    )
    identity = current_gate_identity(str(tmp_path), "sess-test")
    ev = verdict_evidence(identity, "PASS")
    ev["authority"] = "manual"
    mirror_gate_verdict(tmp_path, "PASS", evidence=ev)

    res = finish_analyze(
        MbFinishRequest(
            phase="BACK ANALYZE",
            step_id="ANALYZE",
            done_summary="missing analyze yaml",
            cwd=str(tmp_path),
        )
    )
    assert res.ok is False
    assert "analyze_gate_pending" in res.diagnostic_codes
    assert "analyze_missing" in res.diagnostic_codes
    written = read_active_context(tmp_path)
    assert "mode: IMPLEMENT" not in written
    assert "mode: ANALYZE" in written


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
    assert res.next_phase == "QA"

    written = read_active_context(tmp_path)
    assert "mode: QA" in written
    assert "## Handoff BACK QA" in written

    events = (
        tmp_path
        / "memory-bank"
        / "back"
        / "events"
        / "T-TEST-001"
        / "events.jsonl"
    )
    assert events.is_file()
    lines = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(e.get("kind") == "audit_done" for e in lines)

    from harness.hooks.epic.core import load_epic_state, reduce_epic_lifecycle

    st = load_epic_state(tmp_path)
    assert st.get("phase") == "QA"
    assert st.get("armed_step") == "QA"
    assert st.get("last_finished_step") == "AUDIT"
    life = reduce_epic_lifecycle(tmp_path, "back", "T-TEST-001")
    assert life.get("phase") == "QA"


def test_finish_audit_v2_layout_path_emits_audit_done(tmp_path: Path):
    """finish_audit finds yaml/audit.yaml and emits audit_done without touching _declared_artifacts."""
    audit_dir = tmp_path / "memory-bank" / "back" / "audit" / "T-TEST-V2" / "yaml"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "audit.yaml").write_text(
        "epic_id: T-TEST-V2\nstatus: PASS\nfindings: []\n",
        encoding="utf-8",
    )
    save_epic_state(tmp_path, {"armed_epic": "T-TEST-V2", "armed_role": "BACK"})

    res = finish_audit(
        MbFinishRequest(
            phase="BACK AUDIT",
            step_id="s07",
            done_summary="audit v2",
            cwd=str(tmp_path),
        )
    )
    assert res.ok is True, res.diagnostic_codes
    events = tmp_path / "memory-bank" / "back" / "events" / "T-TEST-V2" / "events.jsonl"
    assert events.is_file()
    body = events.read_text(encoding="utf-8")
    assert "audit_done" in body
    assert "yaml/audit.yaml" in body


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
    assert hasattr(res, "finished_step")
    assert hasattr(res, "next_step")
    assert hasattr(res, "next_phase")
    assert hasattr(res, "epic_done")


def test_finish_analyze_next_typed_fields(tmp_path: Path):
    """cp1: MbFinishResult contains finished_step + next_step fields; on normal finish next_step != finished_step."""
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "back" / "plan").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "back" / "plan" / "plan-T-TEST-001.md").write_text(
        "# plan\n", encoding="utf-8"
    )

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-TEST-001\n"
        "role: back\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-env.yaml\n"
        "  status: pending\n"
        "  next_phase: BACK IMPLEMENT\n",
        encoding="utf-8",
    )
    (mb_dir / "s01-env.yaml").write_text(
        "schema: epic-decompose/v1\nstep_id: s01\nneeds_creative: 'no'\n",
        encoding="utf-8",
    )
    analyze_dir = tmp_path / "memory-bank" / "back" / "analyze" / "T-TEST-001"
    analyze_dir.mkdir(parents=True, exist_ok=True)
    (analyze_dir / "analyze-20260902-pass.yaml").write_text(
        "schema: epic-analyze/v1\n"
        "status: complete\n"
        "metrics:\n"
        "  critical_count: 0\n",
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
            "role": "BACK",
        },
    )

    identity = current_gate_identity(str(tmp_path), "sess-test")
    ev = verdict_evidence(identity, "PASS")
    ev["authority"] = "manual"
    mirror_gate_verdict(tmp_path, "PASS", evidence=ev)

    req = MbFinishRequest(
        phase="BACK ANALYZE",
        step_id="ANALYZE",
        done_summary="analyze complete",
        cwd=str(tmp_path),
    )

    res = finish_analyze(req)
    assert res.ok is True
    assert res.finished_step == "ANALYZE"
    assert res.next_step == "s01"
    assert res.next_phase == "BACK IMPLEMENT"
    assert res.next_step != res.finished_step
    assert res.epic_done is False


def test_mb_finish_pass_hint_emitted(tmp_path: Path):
    """cp3 / FR-007: PASS path always emits mb-finish hint via mb_finish_hint_after_verdict."""
    from loop.mb_finish.verify_hint import mb_finish_hint_after_verdict

    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-TEST-001",
            "armed_step": "s03",
        },
    )
    hint = mb_finish_hint_after_verdict("verify-implement", "PASS", tmp_path)
    assert hint is not None
    assert "mb-finish implement" in hint
    assert "--step s03" in hint
    assert "FORBIDDEN: ручной Write activeContext" in hint

