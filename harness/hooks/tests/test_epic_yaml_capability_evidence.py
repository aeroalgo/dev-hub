from __future__ import annotations

import json
from pathlib import Path
import pytest

from harness.hooks.epic_yaml import (
    EpicDecomposeDoc,
    EpicImplementDoc,
    validate_implement_yaml,
    validate_shard_yaml_full,
    implement_ready_for_finalize_doc,
)
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    compute_declaration_fingerprint,
)
from loop.stack_profiles.evidence import write_capability_evidence


def _create_shard_pair(
    root: Path,
    role: str = "back",
    epic_id: str = "T-APP-001",
    step_id: str = "s01",
    capability_checks: list[dict] | None = None,
    tests: list[str] | None = None,
    verification_results: list[str] | None = None,
) -> tuple[Path, Path]:
    steps_dir = root / "memory-bank" / role / "plan" / epic_id / "yaml" / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = root / "memory-bank" / role / "implement" / epic_id
    impl_dir.mkdir(parents=True, exist_ok=True)

    dec_path = steps_dir / f"{step_id}-test-step.yaml"
    impl_path = impl_dir / f"{step_id}-test-step.yaml"

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
        "decompose_ref": str(dec_path.relative_to(root)),
        "done": ["Did work"],
        "files": ["app/main.py"],
        "integration_check": ["Checked"],
        "tests": tests or [],
        "verification_results": verification_results or [],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "status": "done"}],
    }
    impl_path.write_text(json.dumps(impl_doc), encoding="utf-8")

    # Create dummy app file
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "main.py").write_text("# main\n", encoding="utf-8")

    return dec_path, impl_path


def test_managed_capability_requires_matching_evidence(tmp_path: Path) -> None:
    """validate-step accepts managed capability checks when valid matching evidence sidecar exists."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )

    # Without evidence: must fail with capability_evidence_missing_or_mismatch
    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_missing_or_mismatch" in e for e in errors)

    # Write valid matching evidence
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
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    write_capability_evidence(tmp_path, evidence)

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors


def test_managed_capability_rejects_tests_only_proof(tmp_path: Path) -> None:
    """Raw tests: string alone cannot satisfy a managed capability declaration."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=["`bin/pytest tests/test_api.py -q` — PASS"],
    )

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_missing_or_mismatch" in e for e in errors)


def test_managed_capability_rejects_stale_or_foreign_evidence(tmp_path: Path) -> None:
    """Evidence bound to wrong step, epic, role, target or declaration is rejected."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )

    # Evidence for step s02 instead of s01
    fp_s02 = compute_declaration_fingerprint("back", "T-APP-001", "s02", spec)
    evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp_s02,
        role="back",
        epic_id="T-APP-001",
        step_id="s02",
        target="api",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    write_capability_evidence(tmp_path, evidence)

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_missing_or_mismatch" in e for e in errors)


def test_hub_test_fixture_remains_valid_without_executor(tmp_path: Path) -> None:
    """Hub test step (no capability_checks) remains valid with standard tests: entry and zero executor calls."""
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-HUB-076",
        step_id="s05",
        capability_checks=[],
        tests=["`bin/pytest harness/hooks/tests/test_foo.py -q` — PASS"],
    )

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors


def test_finish_rejects_non_authoritative_provenance(tmp_path: Path) -> None:
    """FR-005 / cp2: finish validation rejects sidecar with missing or non-executor provenance with capability_evidence_non_authoritative."""
    from loop.stack_profiles.evidence import get_evidence_relative_path

    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )

    # 1. Write sidecar with agent provenance (forged)
    fp = compute_declaration_fingerprint("back", "T-APP-001", "s01", spec)
    rel_p = get_evidence_relative_path(
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        fingerprint=fp,
    )
    sidecar_path = tmp_path / rel_p
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    fake_payload = {
        "declaration_fingerprint": fp,
        "role": "back",
        "epic_id": "T-APP-001",
        "step_id": "s01",
        "target": "api",
        "capability": "test.full",
        "status": "succeeded",
        "exit_code": 0,
        "duration_ms": 120,
        "recorded_at": "2026-09-07T12:00:00Z",
        "provenance_source": "agent",
    }
    sidecar_path.write_text(json.dumps(fake_payload), encoding="utf-8")

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_non_authoritative" in e for e in errors)

    impl_doc = EpicImplementDoc.model_validate(json.loads(impl_path.read_text(encoding="utf-8")))
    ready_errs = implement_ready_for_finalize_doc(impl_doc, cwd=tmp_path)
    assert any("capability_evidence_non_authoritative" in e for e in ready_errs)

    # 2. Write sidecar with missing provenance (legacy / unprovenanced)
    del fake_payload["provenance_source"]
    sidecar_path.write_text(json.dumps(fake_payload), encoding="utf-8")

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_non_authoritative" in e for e in errors)

    # 3. Legitimate executor-written sidecar passes
    evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        target="api",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    write_capability_evidence(tmp_path, evidence)

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors
def test_forged_capability_evidence_fails_finish(tmp_path: Path) -> None:
    """Forged capability evidence with agent provenance fails finish validation."""
    from loop.stack_profiles.evidence import get_evidence_relative_path

    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )

    fp = compute_declaration_fingerprint("back", "T-APP-001", "s01", spec)
    rel_p = get_evidence_relative_path(
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        fingerprint=fp,
    )
    sidecar_path = tmp_path / rel_p
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    fake_payload = {
        "declaration_fingerprint": fp,
        "role": "back",
        "epic_id": "T-APP-001",
        "step_id": "s01",
        "target": "api",
        "capability": "test.full",
        "status": "succeeded",
        "exit_code": 0,
        "duration_ms": 120,
        "recorded_at": "2026-09-07T12:00:00Z",
        "provenance_source": "agent",
    }
    sidecar_path.write_text(json.dumps(fake_payload), encoding="utf-8")

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_non_authoritative" in e for e in errors)

    impl_doc = EpicImplementDoc.model_validate(json.loads(impl_path.read_text(encoding="utf-8")))
    ready_errs = implement_ready_for_finalize_doc(impl_doc, cwd=tmp_path)
    assert any("capability_evidence_non_authoritative" in e for e in ready_errs)


def test_unprovenanced_capability_evidence_fails_finish(tmp_path: Path) -> None:
    """Capability evidence lacking provenance_source fails finish validation."""
    from loop.stack_profiles.evidence import get_evidence_relative_path

    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )

    fp = compute_declaration_fingerprint("back", "T-APP-001", "s01", spec)
    rel_p = get_evidence_relative_path(
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        fingerprint=fp,
    )
    sidecar_path = tmp_path / rel_p
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    fake_payload = {
        "declaration_fingerprint": fp,
        "role": "back",
        "epic_id": "T-APP-001",
        "step_id": "s01",
        "target": "api",
        "capability": "test.full",
        "status": "succeeded",
        "exit_code": 0,
        "duration_ms": 120,
        "recorded_at": "2026-09-07T12:00:00Z",
    }
    sidecar_path.write_text(json.dumps(fake_payload), encoding="utf-8")

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_non_authoritative" in e for e in errors)


def test_write_capability_evidence(tmp_path: Path) -> None:
    """CP3: Executor/check-after programmatic writes write capability sidecars without pretool interception."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
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
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    sidecar_path = write_capability_evidence(tmp_path, evidence)
    assert sidecar_path.exists()
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert data["declaration_fingerprint"] == fp
    assert data["status"] == "succeeded"


def test_valid_capability_evidence(tmp_path: Path) -> None:
    """CP3: Legitimately written evidence with executor provenance succeeds in validate_implement_yaml and finalize-step."""
    spec = CapabilityCheckSpec(target="api", capability="test.full")
    dec_path, impl_path = _create_shard_pair(
        tmp_path,
        role="back",
        epic_id="T-APP-001",
        step_id="s01",
        capability_checks=[spec.model_dump()],
        tests=[],
    )
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
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    write_capability_evidence(tmp_path, evidence)

    errors, warnings = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors

    impl_doc = EpicImplementDoc.model_validate(json.loads(impl_path.read_text(encoding="utf-8")))
    ready_errs = implement_ready_for_finalize_doc(impl_doc, cwd=tmp_path)
    assert not ready_errs
