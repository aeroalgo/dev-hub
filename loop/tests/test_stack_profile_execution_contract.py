"""Tests for capability check spec, result, evidence, and declaration fingerprint."""

import pytest
from pydantic import ValidationError

from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    CapabilityExecutionResult,
    compute_declaration_fingerprint,
)
from loop.stack_profiles.schemas import CapabilityName, Diagnostic


def test_capability_check_spec_requires_named_target():
    # Valid spec
    spec = CapabilityCheckSpec(
        target="api",
        capability=CapabilityName.TEST_FULL,
    )
    assert spec.target == "api"
    assert spec.capability == CapabilityName.TEST_FULL
    assert spec.selector is None

    # Missing target must fail
    with pytest.raises(ValidationError) as exc:
        CapabilityCheckSpec.model_validate({"capability": "test.full"})
    assert "target" in str(exc.value)

    # Empty target must fail
    with pytest.raises(ValidationError) as exc:
        CapabilityCheckSpec(target="", capability=CapabilityName.TEST_FULL)
    assert "target" in str(exc.value)

    # test.targeted requires selector
    with pytest.raises(ValidationError) as exc:
        CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_TARGETED)
    assert "selector" in str(exc.value)

    # test.full forbids selector
    with pytest.raises(ValidationError) as exc:
        CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_FULL, selector="tests/test_x.py")
    assert "selector" in str(exc.value)


def test_capability_check_spec_rejects_raw_process_fields():
    raw_fields = [
        {"target": "api", "capability": "test.full", "command": "pytest"},
        {"target": "api", "capability": "test.full", "argv": ["pytest"]},
        {"target": "api", "capability": "test.full", "cwd": "services/api"},
        {"target": "api", "capability": "test.full", "env": {"FOO": "bar"}},
        {"target": "api", "capability": "test.full", "environment": {"FOO": "bar"}},
        {"target": "api", "capability": "test.full", "profile": "python"},
        {"target": "api", "capability": "test.full", "timeout": 30},
        {"target": "api", "capability": "test.full", "timeout_seconds": 30},
    ]
    for raw in raw_fields:
        with pytest.raises(ValidationError) as exc:
            CapabilityCheckSpec.model_validate(raw)
        err_msg = str(exc.value)
        assert "Extra inputs are not permitted" in err_msg or "extra" in err_msg.lower()


def test_capability_check_spec_rejects_unknown_fields():
    with pytest.raises(ValidationError) as exc:
        CapabilityCheckSpec.model_validate({
            "target": "api",
            "capability": "test.full",
            "unknown_field": "some_value",
        })
    assert "extra" in str(exc.value).lower() or "Extra inputs are not permitted" in str(exc.value)


def test_declaration_fingerprint_is_canonical_and_target_bound():
    spec1 = CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_FULL)
    spec2 = CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_FULL)

    fp1 = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-076",
        step_id="s01",
        declaration=spec1,
    )
    fp2 = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-076",
        step_id="s01",
        declaration=spec2,
    )
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # sha256 hex string

    # Target change changes fingerprint
    spec_worker = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    fp_worker = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-076",
        step_id="s01",
        declaration=spec_worker,
    )
    assert fp_worker != fp1

    # Role/epic/step change changes fingerprint
    fp_diff_step = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-076",
        step_id="s02",
        declaration=spec1,
    )
    assert fp_diff_step != fp1

    fp_diff_epic = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-077",
        step_id="s01",
        declaration=spec1,
    )
    assert fp_diff_epic != fp1

    fp_diff_role = compute_declaration_fingerprint(
        role="integ",
        epic_id="T-HUB-076",
        step_id="s01",
        declaration=spec1,
    )
    assert fp_diff_role != fp1


def test_capability_execution_result_and_evidence_schema():
    # Valid result
    res = CapabilityExecutionResult(
        ok=True,
        target="api",
        profile="python",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=150,
        diagnostics=[],
    )
    assert res.schema_version == "stack-capability-execution/v1"
    assert res.status == "succeeded"

    # Forbid raw stdout/body in evidence
    with pytest.raises(ValidationError):
        CapabilityExecutionResult.model_validate({
            "ok": True,
            "target": "api",
            "profile": "python",
            "capability": "test.full",
            "status": "succeeded",
            "exit_code": 0,
            "duration_ms": 100,
            "stdout": "raw body",
        })

    # Evidence model
    spec = CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_FULL)
    fp = compute_declaration_fingerprint(
        role="back",
        epic_id="T-HUB-076",
        step_id="s01",
        declaration=spec,
    )
    evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp,
        role="back",
        epic_id="T-HUB-076",
        step_id="s01",
        target="api",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=150,
        recorded_at="2026-09-07T12:00:00Z",
    )
    assert evidence.schema_version == "stack-capability-evidence/v1"
    assert evidence.declaration_fingerprint == fp
