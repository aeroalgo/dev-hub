from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness.hooks.epic_yaml import (
    EpicImplementDoc,
    validate_shard_yaml_full,
    implement_ready_for_finalize_doc,
)
from loop.context_loop import _enforce_capability_checks_for_armed_step
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    compute_declaration_fingerprint,
)
from loop.stack_profiles.evidence import (
    write_capability_evidence,
    read_capability_evidence,
    get_evidence_relative_path,
)
from loop.stack_profiles.resolver import resolve_capability
from loop.stack_profiles.schemas import CapabilityRequest, DiagnosticCode


@pytest.fixture
def monorepo_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "monorepo"
    repo.mkdir(parents=True)

    # Services
    backend = repo / "services" / "backend"
    backend.mkdir(parents=True)
    (backend / "pyproject.toml").write_text("[project]\nname = 'backend'\n", encoding="utf-8")

    worker = repo / "services" / "worker"
    worker.mkdir(parents=True)
    (worker / "Cargo.toml").write_text("[package]\nname = 'worker'\nversion = '0.1.0'\n", encoding="utf-8")

    web = repo / "apps" / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    (web / "package-lock.json").write_text('{"name": "web", "lockfileVersion": 3}', encoding="utf-8")

    manifest = repo / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
workflow_pack: dev-hub-software
default_target: backend
targets:
  backend:
    root: services/backend
    profile: python
  worker:
    root: services/worker
    profile: rust
  web:
    root: apps/web
    profile: javascript
""",
        encoding="utf-8",
    )
    return repo


def test_independent_test_monorepo_resolve_exact_json(monorepo_fixture: Path) -> None:
    # 1. Python target
    py_res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="backend"),
    )
    assert py_res.ok is True
    assert py_res.diagnostics == []
    assert py_res.profile == "python"
    assert py_res.target == "backend"
    assert py_res.cwd == str((monorepo_fixture / "services" / "backend").resolve())
    assert py_res.argv == ["python", "-m", "pytest"]

    # 2. Rust target
    rust_res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="worker"),
    )
    assert rust_res.ok is True
    assert rust_res.diagnostics == []
    assert rust_res.profile == "rust"
    assert rust_res.target == "worker"
    assert rust_res.cwd == str((monorepo_fixture / "services" / "worker").resolve())
    assert rust_res.argv == ["cargo", "test", "--all-targets"]

    # 3. JavaScript target
    js_res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="web"),
    )
    assert js_res.ok is True
    assert js_res.diagnostics == []
    assert js_res.profile == "javascript"
    assert js_res.target == "web"
    assert js_res.cwd == str((monorepo_fixture / "apps" / "web").resolve())
    assert js_res.argv == ["npm", "run", "test"]


def test_independent_test_cli_api_json_parity(monorepo_fixture: Path) -> None:
    api_res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="backend"),
    )
    api_dict = api_res.model_dump(by_alias=True)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.stack_profiles",
            "resolve",
            "--project-root",
            str(monorepo_fixture),
            "--capability",
            "test.full",
            "--target",
            "backend",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    cli_dict = json.loads(proc.stdout)
    assert cli_dict == api_dict


def test_independent_test_negatives_drop_default_target(monorepo_fixture: Path) -> None:
    manifest = monorepo_fixture / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
workflow_pack: dev-hub-software
targets:
  backend:
    root: services/backend
    profile: python
  worker:
    root: services/worker
    profile: rust
""",
        encoding="utf-8",
    )
    res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full"),
    )
    assert res.ok is False
    assert res.argv == []
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "target_selection_required"


def test_independent_test_negatives_second_js_lockfile(monorepo_fixture: Path) -> None:
    web = monorepo_fixture / "apps" / "web"
    (web / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4\n", encoding="utf-8")

    res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="web"),
    )
    assert res.ok is False
    assert res.argv == []
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "js_package_manager_ambiguous"


def test_independent_test_negatives_target_root_escape(monorepo_fixture: Path) -> None:
    manifest = monorepo_fixture / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
workflow_pack: dev-hub-software
targets:
  escaped:
    root: ../outside
    profile: python
""",
        encoding="utf-8",
    )
    res = resolve_capability(
        monorepo_fixture,
        CapabilityRequest(capability="test.full", target="escaped"),
    )
    assert res.ok is False
    assert res.argv == []
    assert len(res.diagnostics) == 1
    assert res.diagnostics[0].code == "target_root_unsafe"


def test_hub_self_test_canon_locked() -> None:
    from harness.hooks.test_run_canon import BIN_PYTEST_PREFIX, PYTEST_PREFIX
    from loop.incidents.schema import IncidentRecord
    from loop.incidents.tier1_verify import build_verify_ac_slice

    assert BIN_PYTEST_PREFIX == "bin/pytest "
    assert PYTEST_PREFIX == ".venv/bin/pytest "

    incident = IncidentRecord(
        incident_id="test_inc_id",
        project_root="/tmp",
        epic_id="E1",
        step_id="s01",
        session_id="sess1",
        source="test",
        phase="BACK IMPLEMENT",
        opened_at="2026-09-07T00:00:00Z",
        diagnostic_codes=["active_context_shape_invalid"],
        fingerprint="fp1",
    )
    cmds = build_verify_ac_slice(incident, "/tmp")
    assert all(".venv/bin/pytest" in cmd for cmd in cmds)
    assert not any("cargo" in cmd or "npm" in cmd for cmd in cmds)


def test_managed_capability_scenarios_deny_halt(tmp_path: Path) -> None:
    """Validate all TM-I2-076-01 through TM-I2-076-05 scenarios and fail-closed deny on missing checks."""
    # --- Setup Managed Workspace Fixture ---
    managed_root = tmp_path / "managed_workspace"
    managed_root.mkdir(parents=True)
    (managed_root / "services" / "backend").mkdir(parents=True)
    (managed_root / "services" / "backend" / "pyproject.toml").write_text("[project]\nname='backend'\n", encoding="utf-8")

    manifest_data = {
        "schema": "dev-hub-project/v1",
        "workflow_pack": "dev-hub-software",
        "default_target": "backend",
        "targets": {
            "backend": {
                "root": "services/backend",
                "profile": "python",
            }
        },
    }
    (managed_root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    role = "back"
    epic_id = "T-APP-001"
    step_id = "s01"

    steps_dir = managed_root / "memory-bank" / role / "plan" / epic_id / "yaml" / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = managed_root / "memory-bank" / role / "implement" / epic_id
    impl_dir.mkdir(parents=True, exist_ok=True)

    dec_path = steps_dir / f"{step_id}-test-step.yaml"
    impl_path = impl_dir / f"{step_id}-test-step.yaml"
    index_path = managed_root / "memory-bank" / role / "plan" / epic_id / "yaml" / "decompose-index.yaml"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        f"schema: epic-decompose-index/v1\nplan_id: {epic_id}\nsteps:\n  - id: {step_id}\n    file: steps/{step_id}-test-step.yaml\n    title: Step {step_id}\n    status: pending\n",
        encoding="utf-8",
    )

    # 1. TM-I2-076-01: Managed root + shard only hub tests: -> finish denied with managed_verification_requires_capability_checks
    dec_doc_no_caps = {
        "schema": "epic-decompose/v1",
        "role": role,
        "step_id": step_id,
        "plan_id": epic_id,
        "title": "Test Step",
        "next_phase": "BACK IMPLEMENT",
        "goal": "Outcome goal",
        "delta": ["Some change"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "verify": "bin/pytest tests/test_foo.py -q"}],
        "capability_checks": [],
    }
    dec_path.write_text(yaml.safe_dump(dec_doc_no_caps), encoding="utf-8")

    impl_doc_data = {
        "schema": "epic-implement/v1",
        "role": role,
        "step_id": step_id,
        "plan_id": epic_id,
        "title": "Test Step",
        "status": "in_progress",
        "date": "2026-09-14",
        "decompose_ref": str(dec_path.relative_to(managed_root)),
        "done": ["Work done"],
        "files": ["services/backend/pyproject.toml"],
        "integration_check": ["Checked"],
        "tests": ["`bin/pytest tests/test_foo.py -q` — PASS"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "status": "done"}],
    }
    impl_path.write_text(yaml.safe_dump(impl_doc_data), encoding="utf-8")

    errors_01, _ = validate_shard_yaml_full(impl_path, finish=True)
    assert any("managed_verification_requires_capability_checks" in e for e in errors_01)
    ready_errs_01 = implement_ready_for_finalize_doc(EpicImplementDoc.model_validate(impl_doc_data), cwd=managed_root)
    assert any("managed_verification_requires_capability_checks" in e for e in ready_errs_01)

    # 2. TM-I2-076-02: Managed armed step no capability_checks -> check_after / _enforce_capability_checks_for_armed_step halt
    res_02 = _enforce_capability_checks_for_armed_step(
        managed_root,
        decompose=str(index_path.relative_to(managed_root)),
        step_id=step_id,
        state={"role": role, "armed_epic": epic_id},
    )
    assert res_02 is not None
    assert res_02.get("ok") is False
    assert res_02.get("halt") is True
    assert res_02.get("diagnostic_code") == "managed_verification_requires_capability_checks"
    assert "managed_verification_requires_capability_checks" in res_02.get("diagnostic_codes", [])

    # 3. TM-I2-076-03: Agent-forged sidecar with succeeded status -> finish denied with capability_evidence_non_authoritative
    spec = CapabilityCheckSpec(target="backend", capability="test.full")
    dec_doc_with_caps = dict(dec_doc_no_caps)
    dec_doc_with_caps["capability_checks"] = [spec.model_dump(by_alias=True)]
    dec_path.write_text(yaml.safe_dump(dec_doc_with_caps), encoding="utf-8")

    fp = compute_declaration_fingerprint(role, epic_id, step_id, spec)
    rel_sidecar = get_evidence_relative_path(role, epic_id, step_id, fp)
    sidecar_p = managed_root / rel_sidecar
    sidecar_p.parent.mkdir(parents=True, exist_ok=True)

    fake_sidecar = {
        "declaration_fingerprint": fp,
        "role": role,
        "epic_id": epic_id,
        "step_id": step_id,
        "target": "backend",
        "capability": "test.full",
        "status": "succeeded",
        "exit_code": 0,
        "duration_ms": 100,
        "recorded_at": "2026-09-14T00:00:00Z",
        "provenance_source": "agent",
    }
    sidecar_p.write_text(json.dumps(fake_sidecar), encoding="utf-8")

    assert read_capability_evidence(managed_root, role, epic_id, step_id, spec) is None

    errors_03, _ = validate_shard_yaml_full(impl_path, finish=True)
    assert any("capability_evidence_non_authoritative" in e for e in errors_03)
    ready_errs_03 = implement_ready_for_finalize_doc(EpicImplementDoc.model_validate(impl_doc_data), cwd=managed_root)
    assert any("capability_evidence_non_authoritative" in e for e in ready_errs_03)

    # 4. TM-I2-076-04: Hub root without manifest + hub tests -> finish still valid, no capability requirement
    hub_root = tmp_path / "hub_workspace"
    hub_root.mkdir(parents=True)
    hub_steps_dir = hub_root / "memory-bank" / role / "plan" / "T-HUB-001" / "yaml" / "steps"
    hub_steps_dir.mkdir(parents=True, exist_ok=True)
    hub_impl_dir = hub_root / "memory-bank" / role / "implement" / "T-HUB-001"
    hub_impl_dir.mkdir(parents=True, exist_ok=True)

    hub_dec_path = hub_steps_dir / "s01-step.yaml"
    hub_impl_path = hub_impl_dir / "s01-step.yaml"
    hub_index_path = hub_root / "memory-bank" / role / "plan" / "T-HUB-001" / "yaml" / "decompose-index.yaml"
    hub_index_path.parent.mkdir(parents=True, exist_ok=True)
    hub_index_path.write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-HUB-001\nsteps:\n  - id: s01\n    file: steps/s01-step.yaml\n    title: Step s01\n    status: pending\n",
        encoding="utf-8",
    )

    (hub_root / "core").mkdir(parents=True, exist_ok=True)
    (hub_root / "core" / "file.py").write_text("# code\n", encoding="utf-8")

    hub_dec_doc = {
        "schema": "epic-decompose/v1",
        "role": role,
        "step_id": "s01",
        "plan_id": "T-HUB-001",
        "title": "Hub Step",
        "next_phase": "BACK IMPLEMENT",
        "goal": "Hub Goal",
        "delta": ["Hub delta"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "verify": "bin/pytest tests/test_hub.py -q"}],
        "capability_checks": [],
    }
    hub_dec_path.write_text(yaml.safe_dump(hub_dec_doc), encoding="utf-8")

    hub_impl_data = {
        "schema": "epic-implement/v1",
        "role": role,
        "step_id": "s01",
        "plan_id": "T-HUB-001",
        "title": "Hub Step",
        "status": "in_progress",
        "date": "2026-09-14",
        "decompose_ref": str(hub_dec_path.relative_to(hub_root)),
        "done": ["Hub work done"],
        "files": ["core/file.py"],
        "integration_check": ["Hub integration check"],
        "tests": ["`bin/pytest tests/test_hub.py -q` — PASS"],
        "checkpoints": [{"id": "cp1", "criterion": "Done", "status": "done"}],
    }
    hub_impl_path.write_text(yaml.safe_dump(hub_impl_data), encoding="utf-8")

    errors_04, _ = validate_shard_yaml_full(hub_impl_path, finish=True)
    assert not errors_04
    ready_errs_04 = implement_ready_for_finalize_doc(EpicImplementDoc.model_validate(hub_impl_data), cwd=hub_root)
    assert not ready_errs_04
    res_04 = _enforce_capability_checks_for_armed_step(
        hub_root,
        decompose=str(hub_index_path.relative_to(hub_root)),
        step_id="s01",
        state={"role": role, "armed_epic": "T-HUB-001"},
    )
    assert res_04 is None

    # 5. TM-I2-076-05: Executor-written sidecar with provenance -> finish accepts
    legit_evidence = CapabilityExecutionEvidence(
        declaration_fingerprint=fp,
        role=role,
        epic_id=epic_id,
        step_id=step_id,
        target="backend",
        capability="test.full",
        status="succeeded",
        exit_code=0,
        duration_ms=100,
        recorded_at="2026-09-14T00:00:00Z",
        provenance_source="executor",
    )
    write_capability_evidence(managed_root, legit_evidence)

    loaded_ev = read_capability_evidence(managed_root, role, epic_id, step_id, spec)
    assert loaded_ev is not None
    assert loaded_ev.provenance_source == "executor"
    assert loaded_ev.status == "succeeded"

    errors_05, _ = validate_shard_yaml_full(impl_path, finish=True)
    assert not errors_05
    ready_errs_05 = implement_ready_for_finalize_doc(EpicImplementDoc.model_validate(impl_doc_data), cwd=managed_root)
    assert not ready_errs_05
