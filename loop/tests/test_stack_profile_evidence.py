"""Unit and integration tests for CapabilityExecutionEvidence persistence and reader."""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from loop.stack_profiles.evidence import (
    get_evidence_relative_path,
    read_capability_evidence,
    write_capability_evidence,
)
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    CapabilityExecutionResult,
    compute_declaration_fingerprint,
)
from loop.stack_profiles.schemas import CapabilityName, Diagnostic


def _make_sample_evidence(
    role: str = "back",
    epic_id: str = "T-HUB-076",
    step_id: str = "s03",
    target: str = "core",
    capability: CapabilityName = CapabilityName.TEST_FULL,
    selector: str | None = None,
    status: str = "succeeded",
    exit_code: int = 0,
) -> tuple[CapabilityCheckSpec, CapabilityExecutionEvidence]:
    spec = CapabilityCheckSpec(target=target, capability=capability, selector=selector)
    fp = compute_declaration_fingerprint(
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        declaration=spec,
    )
    result = CapabilityExecutionResult(
        ok=(status == "succeeded"),
        target=target,
        profile="python",
        capability=capability.value,
        cwd="/tmp/mock",
        argv=["pytest"],
        timeout_seconds=300,
        status=status,
        exit_code=exit_code,
        duration_ms=120,
    )
    evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp,
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        target=target,
        capability=capability.value,
        status=status,
        exit_code=exit_code,
        duration_ms=120,
        recorded_at="2026-09-07T12:00:00Z",
    )
    return spec, evidence


def test_evidence_write_is_atomic_and_fingerprint_named(tmp_path: Path):
    """cp3: Evidence write is atomic, validated and stored at the deterministic fingerprint path."""
    spec, evidence = _make_sample_evidence()
    rel_path = get_evidence_relative_path(
        role=evidence.role,
        epic_id=evidence.epic_id,
        step_id=evidence.step_id,
        fingerprint=evidence.declaration_fingerprint,
    )
    expected_rel = Path(f"memory-bank/{evidence.role}/execution/{evidence.epic_id}/{evidence.step_id}/capability-{evidence.declaration_fingerprint}.json")
    assert rel_path == expected_rel

    written_path = write_capability_evidence(
        project_root=tmp_path,
        evidence=evidence,
    )
    assert written_path == tmp_path / expected_rel
    assert written_path.exists()

    # Read content and ensure valid json
    raw = json.loads(written_path.read_text(encoding="utf-8"))
    assert raw["schema"] == "stack-capability-evidence/v1"
    assert raw["declaration_fingerprint"] == evidence.declaration_fingerprint
    assert raw["role"] == evidence.role
    assert raw["epic_id"] == evidence.epic_id
    assert raw["step_id"] == evidence.step_id
    assert raw["target"] == evidence.target
    assert raw["capability"] == evidence.capability
    assert raw["status"] == "succeeded"
    assert raw["exit_code"] == 0


def test_evidence_omits_output_body_and_environment(tmp_path: Path):
    """cp3: Evidence never serializes process output bodies (stdout/stderr) or environment secrets."""
    spec, evidence = _make_sample_evidence()
    written_path = write_capability_evidence(
        project_root=tmp_path,
        evidence=evidence,
    )
    raw = json.loads(written_path.read_text(encoding="utf-8"))
    assert "stdout" not in raw
    assert "stderr" not in raw
    assert "env" not in raw
    assert "environment" not in raw
    assert "output" not in raw


def test_evidence_rejects_foreign_role_epic_step_target_and_fingerprint(tmp_path: Path):
    """cp4: Evidence reader rejects foreign role, epic, step, target, or mismatched fingerprint."""
    spec, evidence = _make_sample_evidence(
        role="back",
        epic_id="T-HUB-076",
        step_id="s03",
        target="core",
        capability=CapabilityName.TEST_FULL,
    )
    write_capability_evidence(project_root=tmp_path, evidence=evidence)

    # 1. Matching read succeeds
    loaded = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-076",
        step_id="s03",
        declaration=spec,
    )
    assert loaded is not None
    assert loaded.declaration_fingerprint == evidence.declaration_fingerprint

    # 2. Foreign role -> None / rejected
    loaded_wrong_role = read_capability_evidence(
        project_root=tmp_path,
        role="front",
        epic_id="T-HUB-076",
        step_id="s03",
        declaration=spec,
    )
    assert loaded_wrong_role is None

    # 3. Foreign epic_id -> None / rejected
    loaded_wrong_epic = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-999",
        step_id="s03",
        declaration=spec,
    )
    assert loaded_wrong_epic is None

    # 4. Foreign step_id -> None / rejected
    loaded_wrong_step = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-076",
        step_id="s04",
        declaration=spec,
    )
    assert loaded_wrong_step is None

    # 5. Foreign target -> fingerprint mismatch -> None
    other_spec = CapabilityCheckSpec(target="other_target", capability=CapabilityName.TEST_FULL)
    loaded_wrong_target = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-076",
        step_id="s03",
        declaration=other_spec,
    )
    assert loaded_wrong_target is None

    # 6. Foreign capability -> fingerprint mismatch -> None
    cap_spec = CapabilityCheckSpec(target="core", capability=CapabilityName.TEST_TARGETED, selector="test_foo")
    loaded_wrong_cap = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-076",
        step_id="s03",
        declaration=cap_spec,
    )
    assert loaded_wrong_cap is None
