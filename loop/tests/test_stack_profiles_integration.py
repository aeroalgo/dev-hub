from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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
    # Check tier1_verify uses .venv/bin/pytest and doesn't execute stack profile commands
    cmds = build_verify_ac_slice(incident, "/tmp")
    assert all(".venv/bin/pytest" in cmd for cmd in cmds)
    assert not any("cargo" in cmd or "npm" in cmd for cmd in cmds)
