from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from loop.kernel.engine import LoopEngine
from loop.kernel.index import (
    index_path,
    load_queue,
    plan_path,
)
from loop.kernel.store import LoopPaths
from loop.kernel.verdict import GateVerdict, SCHEMA_GATE_VERDICT


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).lstrip(), encoding="utf-8")
    return path


def _seed_security_project(root: Path, epic_id: str = "T-SEC-01") -> LoopPaths:
    plan_file = plan_path(root, "back", epic_id, kind="security")
    _write(plan_file, f"# Security Plan {epic_id}\n")

    idx_file = index_path(root, "back", epic_id, kind="security")
    index_content = {
        "schema": "epic-decompose-index/v1",
        "role": "back",
        "plan_id": epic_id,
        "steps": [
            {
                "id": "a01",
                "file": "a01-auth.yaml",
                "title": "a01 — auth security review",
                "status": "pending",
            },
            {
                "id": "a02",
                "file": "a02-crypto.yaml",
                "title": "a02 — crypto review",
                "status": "pending",
            },
        ],
    }
    _write(idx_file, yaml.safe_dump(index_content))

    steps_dir = idx_file.parent.parent / "yaml" / "steps"
    for s_id, s_file in [("a01", "a01-auth.yaml"), ("a02", "a02-crypto.yaml")]:
        _write(
            steps_dir / s_file,
            f"""
            schema: epic-decompose/v1
            role: back
            step_id: {s_id}
            plan_id: {epic_id}
            title: {s_id}
            next_phase: BACK SECURITY
            needs_creative: "no"
            goal: audit
            plan_contract:
              fr_ids: []
              nouns: []
              layout_paths: []
              ac_quotes: []
              plan_jumps: []
            context:
              consumes: []
              produces: []
              plan_refs: []
              files: []
            as_built: []
            delta: []
            deletes: []
            out_of_scope: []
            skills:
              code_surface: service
              impl: []
            checkpoints:
              - id: cp1
                criterion: checked
                verify: ""
            verify: []
            tdd: []
            """,
        )

    return LoopPaths(project=root, hub=root / "hub")


def _seed_security_artifact(
    root: Path,
    epic_id: str,
    step_id: str,
    shard_name: str,
    status: str = "in_progress",
) -> Path:
    artifact_path = (
        root
        / "memory-bank"
        / "back"
        / "security"
        / "implement"
        / epic_id
        / shard_name
    )
    return _write(
        artifact_path,
        f"""
        schema: epic-security/v1
        role: back
        step_id: {step_id}
        plan_id: {epic_id}
        title: {step_id} security
        status: {status}
        audit_surface: core
        evidence_commands:
          - "rg token"
        findings: []
        checkpoints:
          - id: cp1
            criterion: verify no leaks
            status: pending
        """,
    )


def test_security_skip_analyze(tmp_path: Path) -> None:
    paths = _seed_security_project(tmp_path, epic_id="T-SEC-SKIP")
    engine = LoopEngine(paths)

    cursor = engine.start("T-SEC-SKIP", role="back")
    assert cursor.kind == "security"
    assert cursor.phase == "SECURITY"
    assert cursor.step_id == "a01"


def test_security_finish_advance(tmp_path: Path) -> None:
    epic_id = "T-SEC-ADV"
    paths = _seed_security_project(tmp_path, epic_id=epic_id)
    engine = LoopEngine(paths)

    cursor = engine.start(epic_id, role="back")
    assert cursor.phase == "SECURITY"
    assert cursor.step_id == "a01"

    _seed_security_artifact(tmp_path, epic_id, "a01", "a01-auth.yaml")

    gate_pass = GateVerdict.model_construct(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-security",
        verdict="PASS",
        session_id=cursor.session_id,
        epic_id=epic_id,
        step_id="a01",
        evidence_id="ev-test",
        recorded_at="2026-10-24T12:00:00+00:00",
    )
    transition = engine.finish(step_id="a01", gate_pass=gate_pass)
    assert transition.phase == "SECURITY"
    assert transition.step_id == "a02"

    idx = load_queue(tmp_path, "back", epic_id, kind="security")
    assert idx.steps[0].status == "completed"
    assert idx.steps[1].status == "pending"


def test_security_queue_complete_done(tmp_path: Path) -> None:
    epic_id = "T-SEC-DONE"
    paths = _seed_security_project(tmp_path, epic_id=epic_id)
    engine = LoopEngine(paths)

    cursor = engine.start(epic_id, role="back")
    assert cursor.phase == "SECURITY"
    assert cursor.step_id == "a01"

    _seed_security_artifact(tmp_path, epic_id, "a01", "a01-auth.yaml")
    gate_pass = GateVerdict.model_construct(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-security",
        verdict="PASS",
        session_id=cursor.session_id,
        epic_id=epic_id,
        step_id="a01",
        evidence_id="ev-test",
        recorded_at="2026-10-24T12:00:00+00:00",
    )
    engine.finish(step_id="a01", gate_pass=gate_pass)

    _seed_security_artifact(tmp_path, epic_id, "a02", "a02-crypto.yaml")
    gate_pass = GateVerdict.model_construct(
        schema=SCHEMA_GATE_VERDICT,
        agent_id="verify-security",
        verdict="PASS",
        session_id=cursor.session_id,
        epic_id=epic_id,
        step_id="a02",
        evidence_id="ev-test",
        recorded_at="2026-10-24T12:00:00+00:00",
    )
    final_transition = engine.finish(step_id="a02", gate_pass=gate_pass)

    assert final_transition.phase == "DONE"
    assert final_transition.step_id == "DONE"
    assert final_transition.status.value == "complete"

    idx = load_queue(tmp_path, "back", epic_id, kind="security")
    assert all(step.status == "completed" for step in idx.steps)
