"""Integration tests asserting exact argv, cwd, shell=False for py, rs, and js targets."""

from pathlib import Path
import subprocess
import pytest
import yaml

from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    execute_capability,
)
from loop.stack_profiles.schemas import CapabilityName


def create_polyglot_project(tmp_path: Path) -> Path:
    """Create a polyglot monorepo fixture with Python, Rust, and JavaScript targets."""
    project_root = tmp_path / "polyglot_workspace"
    project_root.mkdir()

    # 1. Rust target
    (project_root / "crates" / "api").mkdir(parents=True)
    (project_root / "crates" / "api" / "Cargo.toml").write_text("[package]\nname='api'\n", encoding="utf-8")

    # 2. Python target
    (project_root / "services" / "worker").mkdir(parents=True)
    (project_root / "services" / "worker" / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")

    # 3. JavaScript target
    (project_root / "apps" / "web").mkdir(parents=True)
    (project_root / "apps" / "web" / "package.json").write_text('{"name": "web"}\n', encoding="utf-8")
    (project_root / "apps" / "web" / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4\n", encoding="utf-8")

    manifest = {
        "schema": "dev-hub-project/v1",
        "default_target": "api",
        "targets": {
            "api": {
                "root": "crates/api",
                "profile": "rust",
            },
            "worker": {
                "root": "services/worker",
                "profile": "python",
            },
            "web": {
                "root": "apps/web",
                "profile": "javascript",
            },
        },
    }
    (project_root / "dev-hub.project.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return project_root


def test_executor_uses_resolver_exact_argv_cwd_and_shell_false(tmp_path: Path, monkeypatch):
    """Executor calls subprocess.Popen with exact resolver argv, cwd, shell=False, and timeout."""
    project_root = create_polyglot_project(tmp_path)

    recorded_popen_calls = []

    class MockProcess:
        def __init__(self, argv, cwd=None, shell=False, stdout=None, stderr=None, **kwargs):
            recorded_popen_calls.append({
                "argv": argv,
                "cwd": cwd,
                "shell": shell,
                "kwargs": kwargs,
            })
            self.returncode = 0

        def communicate(self, timeout=None):
            return (b"mock stdout", b"")

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    # 1. Rust test.full
    spec_rust = CapabilityCheckSpec(target="api", capability=CapabilityName.TEST_FULL)
    res_rust = execute_capability(project_root, spec_rust)
    assert res_rust.ok is True
    assert res_rust.status == "succeeded"
    assert res_rust.profile == "rust"
    assert len(recorded_popen_calls) == 1
    call_rust = recorded_popen_calls[-1]
    assert call_rust["argv"] == ["cargo", "test", "--all-targets"]
    assert call_rust["cwd"] == str((project_root / "crates" / "api").resolve())
    assert call_rust["shell"] is False

    # 2. Python test.full
    spec_py = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res_py = execute_capability(project_root, spec_py)
    assert res_py.ok is True
    assert res_py.status == "succeeded"
    assert res_py.profile == "python"
    assert len(recorded_popen_calls) == 2
    call_py = recorded_popen_calls[-1]
    assert call_py["argv"] == ["python", "-m", "pytest"]
    assert call_py["cwd"] == str((project_root / "services" / "worker").resolve())
    assert call_py["shell"] is False

    # 3. JavaScript (pnpm) test.full
    spec_js = CapabilityCheckSpec(target="web", capability=CapabilityName.TEST_FULL)
    res_js = execute_capability(project_root, spec_js)
    assert res_js.ok is True
    assert res_js.status == "succeeded"
    assert res_js.profile == "javascript"
    assert len(recorded_popen_calls) == 3
    call_js = recorded_popen_calls[-1]
    assert call_js["argv"] == ["pnpm", "run", "test"]
    assert call_js["cwd"] == str((project_root / "apps" / "web").resolve())
    assert call_js["shell"] is False


def test_executor_runs_each_explicit_python_rust_and_javascript_target_once(tmp_path: Path, monkeypatch):
    """Each explicit target runs exactly once with resolver timeout and no ambient retry."""
    project_root = create_polyglot_project(tmp_path)

    run_counts = {"api": 0, "worker": 0, "web": 0}

    class MockProcess:
        def __init__(self, argv, cwd=None, **kwargs):
            if "crates/api" in str(cwd):
                run_counts["api"] += 1
            elif "services/worker" in str(cwd):
                run_counts["worker"] += 1
            elif "apps/web" in str(cwd):
                run_counts["web"] += 1
            self.returncode = 0

        def communicate(self, timeout=None):
            assert timeout == 300  # Default bundled profile timeout
            return (b"", b"")

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    for target in ["api", "worker", "web"]:
        spec = CapabilityCheckSpec(target=target, capability=CapabilityName.TEST_FULL)
        res = execute_capability(project_root, spec)
        assert res.ok is True

    assert run_counts == {"api": 1, "worker": 1, "web": 1}
