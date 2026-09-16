"""Unit and integration tests for CapabilityExecutionEvidence persistence, schema provenance and reader."""

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
from pydantic import ValidationError

from loop.stack_profiles import __main__ as stack_profiles_cli
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
    execute_capability,
)
from loop.stack_profiles.schemas import CapabilityName, Diagnostic, DiagnosticCode


def _make_sample_evidence(
    role: str = "back",
    epic_id: str = "T-HUB-076",
    step_id: str = "s03",
    target: str = "core",
    capability: CapabilityName = CapabilityName.TEST_FULL,
    selector: str | None = None,
    status: str = "succeeded",
    exit_code: int = 0,
    provenance_source: str = "executor",
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
        provenance_source=provenance_source,
    )
    return spec, evidence


def test_provenance_schema():
    """cp1: CapabilityExecutionEvidence schema enforces provenance_source field and serialization."""
    spec, evidence = _make_sample_evidence()
    assert evidence.provenance_source == "executor"

    dumped = evidence.model_dump(by_alias=True)
    assert dumped["provenance_source"] == "executor"

    # Valid validation from dict with executor provenance
    validated = CapabilityExecutionEvidence.model_validate(dumped)
    assert validated.provenance_source == "executor"

    # Rejection of invalid provenance sources
    with pytest.raises(ValidationError):
        _make_sample_evidence(provenance_source="agent")

    with pytest.raises(ValidationError):
        _make_sample_evidence(provenance_source="manual")

    with pytest.raises(ValidationError):
        _make_sample_evidence(provenance_source="untrusted")


def test_evidence_provenance_authority(tmp_path: Path):
    """cp2: write_capability_evidence stamps executor provenance and read_capability_evidence rejects unprovenanced or agent-forged sidecars."""
    spec, evidence = _make_sample_evidence(
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        target="core",
        capability=CapabilityName.TEST_FULL,
    )
    # 1. Authoritative write and read
    written_path = write_capability_evidence(project_root=tmp_path, evidence=evidence)
    assert written_path.exists()

    raw = json.loads(written_path.read_text(encoding="utf-8"))
    assert raw["provenance_source"] == "executor"

    loaded = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        declaration=spec,
    )
    assert loaded is not None
    assert loaded.provenance_source == "executor"

    # 2. Sidecar missing provenance_source (unprovenanced / legacy / forged)
    raw_unprovenanced = dict(raw)
    del raw_unprovenanced["provenance_source"]
    written_path.write_text(json.dumps(raw_unprovenanced, indent=2), encoding="utf-8")

    loaded_unprovenanced = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        declaration=spec,
    )
    assert loaded_unprovenanced is None

    # 3. Sidecar with non-executor provenance_source (agent-forged)
    raw_forged = dict(raw)
    raw_forged["provenance_source"] = "agent"
    written_path.write_text(json.dumps(raw_forged, indent=2), encoding="utf-8")

    loaded_forged = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        declaration=spec,
    )
    assert loaded_forged is None




def test_read_capability_evidence_forged(tmp_path: Path):
    """Forged capability evidence with agent provenance is rejected by read_capability_evidence."""
    spec, evidence = _make_sample_evidence(
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        target="core",
        capability=CapabilityName.TEST_FULL,
    )
    written_path = write_capability_evidence(project_root=tmp_path, evidence=evidence)
    raw_forged = json.loads(written_path.read_text(encoding="utf-8"))
    raw_forged["provenance_source"] = "agent"
    written_path.write_text(json.dumps(raw_forged, indent=2), encoding="utf-8")

    loaded_forged = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        declaration=spec,
    )
    assert loaded_forged is None


def test_read_capability_evidence_unprovenanced(tmp_path: Path):
    """Unprovenanced capability evidence without provenance_source is rejected by read_capability_evidence."""
    spec, evidence = _make_sample_evidence(
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        target="core",
        capability=CapabilityName.TEST_FULL,
    )
    written_path = write_capability_evidence(project_root=tmp_path, evidence=evidence)
    raw_unprovenanced = json.loads(written_path.read_text(encoding="utf-8"))
    del raw_unprovenanced["provenance_source"]
    written_path.write_text(json.dumps(raw_unprovenanced, indent=2), encoding="utf-8")

    loaded_unprovenanced = read_capability_evidence(
        project_root=tmp_path,
        role="back",
        epic_id="T-HUB-098",
        step_id="s02",
        declaration=spec,
    )
    assert loaded_unprovenanced is None


def test_evidence_write_is_atomic_and_fingerprint_named(tmp_path: Path):
    """Evidence write is atomic, validated and stored at the deterministic fingerprint path."""
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
    assert raw["provenance_source"] == "executor"


def test_evidence_omits_output_body_and_environment(tmp_path: Path):
    """Evidence never serializes process output bodies (stdout/stderr) or environment secrets."""
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
    """Evidence reader rejects foreign role, epic, step, target, or mismatched fingerprint."""
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


def test_operator_cli_diagnostic_execution_flow_compatibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """NFR-003: operator CLI preserves execution diagnostics in its JSON response."""
    diagnostic = Diagnostic(
        code="command_failed",
        message="Command exited with non-zero status code: 2",
    )
    execution_result = CapabilityExecutionResult(
        ok=False,
        target="core",
        profile="python",
        capability=CapabilityName.TEST_TARGETED.value,
        cwd=str(tmp_path),
        argv=["pytest", "test_foo.py"],
        timeout_seconds=300,
        status="failed",
        exit_code=2,
        duration_ms=1,
        diagnostics=[diagnostic],
    )

    observed: dict[str, object] = {}

    def fake_execute(project_root: Path, declaration: CapabilityCheckSpec) -> CapabilityExecutionResult:
        observed["project_root"] = project_root
        observed["declaration"] = declaration
        return execution_result

    monkeypatch.setattr(stack_profiles_cli, "execute_capability", fake_execute)

    cli_exit = stack_profiles_cli.main(
        [
            "execute",
            "--project-root",
            str(tmp_path),
            "--target",
            "core",
            "--capability",
            CapabilityName.TEST_TARGETED.value,
            "--selector",
            "test_foo.py",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert cli_exit == 2
    assert isinstance(observed["declaration"], CapabilityCheckSpec)
    assert observed["declaration"].target == "core"
    assert payload["status"] == "failed"
    assert len(payload["diagnostics"]) == 1
    assert payload["diagnostics"][0]["code"] == "command_failed"


def test_execute_capability_uses_resolved_argv_without_shell_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """NFR-004: execution passes resolver argv directly with shell disabled."""
    resolved_argv = ["python3", "-c", "import sys; sys.exit(0)"]
    resolution = SimpleNamespace(
        ok=True,
        profile="python",
        argv=resolved_argv,
        cwd=str(tmp_path),
        timeout_seconds=30,
        diagnostics=[],
    )

    observed: dict[str, object] = {}

    monkeypatch.setattr(
        "loop.stack_profiles.execution.resolve_capability",
        lambda *args, **kwargs: resolution,
    )

    orig_popen = subprocess.Popen

    def fake_popen(cmd, *args, **kwargs):
        observed["cmd"] = cmd
        observed["kwargs"] = kwargs
        return orig_popen(cmd, *args, **kwargs)

    monkeypatch.setattr("loop.stack_profiles.execution.subprocess.Popen", fake_popen)

    spec = CapabilityCheckSpec(target="core", capability=CapabilityName.TEST_FULL)
    result = execute_capability(project_root=tmp_path, declaration=spec)

    assert observed["cmd"] == resolved_argv
    assert observed["kwargs"]["shell"] is False
    assert result.argv == resolved_argv
    assert result.status == "succeeded"
