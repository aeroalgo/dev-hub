from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from loop.kernel.engine import LoopEngine, TransitionError
from loop.kernel.index import Queue, Step, index_path, load_queue
from loop.kernel.model import Cursor
from loop.kernel.store import LoopPaths, TransactionPlan
from loop.kernel.security_schema import (
    CHECKPOINT_STATUS_ALIASES,
    SCHEMA_SECURITY,
    STEP_STATUS_ALIASES,
    SecurityArtifact,
    coerce_checkpoint_status,
    coerce_step_status,
    complete_security_artifact,
    flush_security_for_verify,
    security_artifact_problems,
    validate_security_artifact,
)
from loop.kernel.verdict import GateVerdict, SCHEMA_GATE_VERDICT


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")
    return path


def test_coerce_aliases() -> None:
    assert coerce_checkpoint_status("passed") == "done"
    assert coerce_checkpoint_status("PASS") == "done"
    assert coerce_checkpoint_status("pending") == "pending"
    with pytest.raises(ValueError, match="unknown_status"):
        coerce_checkpoint_status("unknown_status")

    assert coerce_step_status("in-progress") == "in_progress"
    assert coerce_step_status("wip") == "in_progress"
    assert coerce_step_status("done") == "completed"
    with pytest.raises(ValueError, match="invalid_status"):
        coerce_step_status("invalid_status")


def test_valid_security_artifact(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "a01.yaml",
        """
        schema: epic-security/v1
        role: back
        step_id: a01
        plan_id: T-SEC-01
        title: a01 — auth security review
        status: wip
        date: 2026-10-24
        audit_surface: auth
        scope_paths:
          - apps/api/
        threats:
          - OWASP focus for this slice
        evidence_commands:
          - "rg dangerous_func"
        findings: []
        decompose_ref: memory-bank/back/security/plan/T-SEC-01/yaml/steps/a01-auth.yaml
        checkpoints:
          - id: cp1
            criterion: findings artifact complete
            status: pass
          - id: cp2
            criterion: verify no leaks
            status: open
        resume_from: cp1
        """,
    )
    model = validate_security_artifact(
        path,
        expected_step_id="a01",
        expected_plan_id="T-SEC-01",
        rewrite=True,
    )
    assert isinstance(model, SecurityArtifact)
    assert model.schema_id == SCHEMA_SECURITY
    assert model.step_id == "a01"
    assert model.plan_id == "T-SEC-01"
    assert model.status == "in_progress"
    assert model.scope_paths == ["apps/api/"]
    assert model.findings == []
    assert len(model.checkpoints) == 2
    assert model.checkpoints[0].status == "done"
    assert model.checkpoints[1].status == "pending"

    # Verify rewrite preserved comments and updated status
    text = path.read_text(encoding="utf-8")
    assert "status: in_progress" in text
    assert "status: done" in text
    assert "status: pending" in text
    assert "status: wip" not in text
    assert "status: pass" not in text


def test_complete_security_artifact(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "a01.yaml",
        """
        schema: epic-security/v1
        role: back
        step_id: a01
        plan_id: T-SEC-01
        status: in_progress
        audit_surface: auth
        evidence_commands:
          - "rg token"
        findings:
          - id: SEC-1
            severity: medium
            title: token leak
        checkpoints:
          - id: cp1
            criterion: findings recorded
            status: pending
        """,
    )
    completed = complete_security_artifact(
        path,
        expected_step_id="a01",
        expected_plan_id="T-SEC-01",
    )
    assert completed.status == "completed"
    assert completed.checkpoints[0].status == "done"

    text = path.read_text(encoding="utf-8")
    assert "status: completed" in text
    assert "status: done" in text
    assert "status: in_progress" not in text
    assert "status: pending" not in text


def test_flush_requires_evidence(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "empty_evidence.yaml",
        """
        schema: epic-security/v1
        role: back
        step_id: a01
        plan_id: T-SEC-01
        status: in_progress
        checkpoints:
          - id: cp1
            criterion: findings recorded
            status: pending
        """,
    )
    with pytest.raises(ValueError, match="evidence empty"):
        flush_security_for_verify(path)


def test_security_finish_invalid(tmp_path: Path) -> None:
    # 1. Invalid schema rejects in validate_security_artifact
    bad_schema = _write(
        tmp_path / "bad_schema.yaml",
        """
        schema: epic-implement/v1
        role: back
        step_id: a01
        plan_id: T-SEC-01
        status: in_progress
        checkpoints:
          - id: cp1
            status: pending
        """,
    )
    with pytest.raises(ValueError, match="unsupported security schema"):
        validate_security_artifact(bad_schema)

    # 2. Problems helper returns problem descriptions
    problems = security_artifact_problems(bad_schema)
    assert len(problems) > 0
    assert any("unsupported security schema" in p for p in problems)

    # 3. Missing file throws FileNotFoundError
    missing_path = tmp_path / "nonexistent.yaml"
    with pytest.raises(FileNotFoundError):
        validate_security_artifact(missing_path)

    # 4. Engine finish fail-closed when artifact is missing or invalid
    project = tmp_path / "project"
    project.mkdir()
    paths = LoopPaths(project=project, hub=tmp_path / "hub")
    engine = LoopEngine(paths)

    idx_file = index_path(project, "back", "T-SEC-01", kind="security")
    idx_file.parent.mkdir(parents=True, exist_ok=True)
    index_data = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "plan_id": "T-SEC-01",
        "steps": [
            {
                "step_id": "a01",
                "title": "Security step 1",
                "status": "in_progress",
                "shard": "a01-auth.yaml",
            },
            {
                "step_id": "a02",
                "title": "Security step 2",
                "status": "pending",
                "shard": "a02-crypto.yaml",
            },
        ],
    }
    idx_file.write_text(yaml.safe_dump(index_data), encoding="utf-8")

    cursor = Cursor(
        epic_id="T-SEC-01",
        role="back",
        phase="SECURITY",
        step_id="a01",
        kind="security",
        session_id="session-security-test",
    )
    engine.store.transact(lambda _c, _t: TransactionPlan(cursor=cursor, event={"event": "start", "phase": "SECURITY"}))
    gate_pass = GateVerdict.model_construct(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-security",
        verdict="PASS",
        session_id=cursor.session_id,
        epic_id="T-SEC-01",
        step_id="a01",
        evidence_id="ev-1",
        recorded_at="2026-10-24T12:00:00+00:00",
    )

    # Finish without artifact -> TransitionError (BN-002, TM-003)
    with pytest.raises(TransitionError, match="invalid security artifact"):
        engine.finish(step_id="a01", gate_pass=gate_pass)

    # Write invalid artifact -> TransitionError
    artifact_path = project / "memory-bank" / "back" / "security" / "implement" / "T-SEC-01" / "a01-auth.yaml"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("schema: invalid/v1\n", encoding="utf-8")

    with pytest.raises(TransitionError, match="invalid security artifact"):
        engine.finish(step_id="a01", gate_pass=gate_pass)

    # Write valid artifact -> finish succeeds and index updated to completed
    valid_yaml = """
    schema: epic-security/v1
    role: back
    step_id: a01
    plan_id: T-SEC-01
    title: a01 — auth security review
    status: in_progress
    evidence_commands:
      - "rg auth"
    findings: []
    checkpoints:
      - id: cp1
        criterion: checked
        status: pending
    """
    _write(artifact_path, valid_yaml)

    # Finish succeeds
    res = engine.finish(step_id="a01", gate_pass=gate_pass)
    reloaded_idx = load_queue(project, "back", "T-SEC-01", kind="security")
    assert reloaded_idx.steps[0].status == "completed"
    assert reloaded_idx.steps[1].status == "pending"
