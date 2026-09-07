from __future__ import annotations

import json
from pathlib import Path
import pytest
from unittest.mock import patch

from harness.hooks.epic.core import finalize_step, validate_finish_integrity
from harness.hooks.epic_yaml import load_implement
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    compute_declaration_fingerprint,
)
from loop.stack_profiles.evidence import write_capability_evidence


def _setup_epic_repo(tmp_path: Path, role: str = "back", epic_id: str = "T-APP-001", step_id: str = "s01", capability_checks: list[dict] | None = None) -> tuple[Path, Path]:
    steps_dir = tmp_path / "memory-bank" / role / "plan" / epic_id / "yaml" / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / role / "implement" / epic_id
    impl_dir.mkdir(parents=True, exist_ok=True)

    dec_path = steps_dir / f"{step_id}-test-step.yaml"
    impl_path = impl_dir / f"{step_id}-test-step.yaml"

    index_path = tmp_path / "memory-bank" / role / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_doc = {
        "schema": "epic-decompose-index/v1",
        "plan_id": epic_id,
        "steps": [{"id": step_id, "file": f"{step_id}-test-step.yaml", "status": "pending"}],
    }
    index_path.write_text(json.dumps(index_doc), encoding="utf-8")

    dec_doc = {
        "schema": "epic-decompose/v1",
        "role": role,
        "step_id": step_id,
        "plan_id": epic_id,
        "title": "Test Step",
        "next_phase": f"{role.upper()} IMPLEMENT",
        "goal": "Outcome goal for test step",
        "delta": ["Some delta change"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "verify": "bin/pytest tests/test_foo.py -q"}],
        "capability_checks": capability_checks or [],
    }
    dec_path.write_text(json.dumps(dec_doc), encoding="utf-8")

    impl_doc = {
        "schema": "epic-implement/v1",
        "role": role,
        "step_id": step_id,
        "plan_id": epic_id,
        "title": "Test Step",
        "status": "in_progress",
        "date": "2026-09-07",
        "decompose_ref": str(dec_path.relative_to(tmp_path)),
        "done": ["Did work"],
        "files": ["app/main.py"],
        "integration_check": ["Checked"],
        "tests": [],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "status": "done"}],
    }
    impl_path.write_text(json.dumps(impl_doc), encoding="utf-8")

    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "main.py").write_text("# main\n", encoding="utf-8")

    return dec_path, impl_path


def test_finish_managed_capability_missing_evidence_blocks_finalize(tmp_path: Path) -> None:
    """Finish step validation rejects finalize if managed declaration evidence is absent."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _setup_epic_repo(tmp_path, capability_checks=[spec.model_dump()])

    res = finalize_step(
        tmp_path,
        decompose=str(dec_path.parent.parent / "decompose-index.yaml"),
        step_id="s01",
        require_verify=False,
    )
    assert res.get("ok") is False
    assert any("capability_evidence_missing_or_mismatch" in str(err) for err in res.get("errors", []))


def test_finish_managed_capability_matching_evidence_allows_finalize(tmp_path: Path) -> None:
    """Finish step validation succeeds when valid evidence matching fingerprint is present."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _setup_epic_repo(tmp_path, capability_checks=[spec.model_dump()])

    fp = compute_declaration_fingerprint("back", "T-APP-001", "s01", spec)
    evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        target="api",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=100,
        recorded_at="2026-09-07T12:00:00Z",
    )
    write_capability_evidence(tmp_path, evidence)

    res = finalize_step(
        tmp_path,
        decompose=str(dec_path.parent.parent / "decompose-index.yaml"),
        step_id="s01",
        require_verify=False,
    )
    assert res.get("ok") is True
    assert res.get("finalized") is True
