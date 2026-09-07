"""Unit and contract tests for resolver-owned stack profile capability executor."""

from pathlib import Path
import subprocess
import pytest

from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionResult,
    execute_capability,
)
from loop.stack_profiles.schemas import CapabilityName, Diagnostic


def create_sample_project(tmp_path: Path) -> Path:
    """Create a minimal workspace with dev-hub.project.yaml and Python/Rust/JS target roots."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    (project_root / "services" / "worker").mkdir(parents=True)
    (project_root / "services" / "worker" / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")

    manifest = (
        "schema: dev-hub-project/v1\n"
        "default_target: worker\n"
        "targets:\n"
        "  worker:\n"
        "    root: services/worker\n"
        "    profile: python\n"
    )
    (project_root / "dev-hub.project.yaml").write_text(manifest, encoding="utf-8")
    return project_root


def test_resolution_failed_does_not_spawn(tmp_path: Path, monkeypatch):
    """Resolver or declaration failure returns resolution_failed and never calls Popen."""
    project_root = create_sample_project(tmp_path)

    # Monkeypatch subprocess.Popen to fail immediately if called
    def _fail_popen(*args, **kwargs):
        raise AssertionError("Popen must not be called on resolution failure")

    monkeypatch.setattr(subprocess, "Popen", _fail_popen)

    # Unknown target
    spec_unknown = CapabilityCheckSpec(target="nonexistent", capability=CapabilityName.TEST_FULL)
    res = execute_capability(project_root, spec_unknown)
    assert res.ok is False
    assert res.status == "resolution_failed"
    assert res.target == "nonexistent"
    assert len(res.diagnostics) > 0
    assert res.diagnostics[0].code == "target_unknown"
    assert res.exit_code is None
    assert res.argv == []
    assert res.cwd is None

    # Missing manifest in empty project
    empty_root = tmp_path / "empty_dir"
    empty_root.mkdir()
    spec_valid = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res_manifest = execute_capability(empty_root, spec_valid)
    assert res_manifest.ok is False
    assert res_manifest.status == "resolution_failed"
    assert res_manifest.diagnostics[0].code == "project_manifest_missing"


def test_spawn_error_has_typed_result(tmp_path: Path, monkeypatch):
    """OSError during subprocess.Popen maps to spawn_failed status."""
    project_root = create_sample_project(tmp_path)

    def _raise_oserror(*args, **kwargs):
        raise OSError("Executable not found: python")

    monkeypatch.setattr(subprocess, "Popen", _raise_oserror)

    spec = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res = execute_capability(project_root, spec)

    assert res.ok is False
    assert res.status == "spawn_failed"
    assert res.target == "worker"
    assert res.profile == "python"
    assert res.capability == "test.full"
    assert res.exit_code is None
    assert len(res.diagnostics) > 0
    assert res.diagnostics[0].code == "spawn_failed"
    assert "Executable not found" in res.diagnostics[0].message
    assert res.argv == ["python", "-m", "pytest"]
    assert res.cwd == str((project_root / "services" / "worker").resolve())


def test_timeout_kills_and_collects_child(tmp_path: Path, monkeypatch):
    """TimeoutExpired triggers kill and wait/collect, returning timed_out status."""
    project_root = create_sample_project(tmp_path)

    killed = False
    waited = False

    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["python", "-m", "pytest"], timeout=timeout)

        def kill(self):
            nonlocal killed
            killed = True

        def wait(self, timeout=None):
            nonlocal waited
            waited = True
            self.returncode = -9
            return self.returncode

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    spec = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res = execute_capability(project_root, spec)

    assert killed is True
    assert waited is True
    assert res.ok is False
    assert res.status == "timed_out"
    assert res.target == "worker"
    assert res.profile == "python"
    assert res.capability == "test.full"
    assert res.exit_code == -9 or res.exit_code is None or res.exit_code == -9
    assert len(res.diagnostics) > 0
    assert res.diagnostics[0].code == "process_timed_out"
    assert "timed out" in res.diagnostics[0].message


def test_nonzero_exit_is_failed_without_retry(tmp_path: Path, monkeypatch):
    """Child process exiting non-zero maps to failed status with recorded exit_code."""
    project_root = create_sample_project(tmp_path)

    spawn_count = 0

    class MockProcess:
        def __init__(self, *args, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            self.returncode = 1

        def communicate(self, timeout=None):
            return (b"FAILED test_foo.py\n", b"some error stderr\n")

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    spec = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res = execute_capability(project_root, spec)

    assert spawn_count == 1  # No retry
    assert res.ok is False
    assert res.status == "failed"
    assert res.exit_code == 1
    assert res.stdout_bytes == len(b"FAILED test_foo.py\n")
    assert res.stderr_bytes == len(b"some error stderr\n")
    assert res.output_truncated is False


def test_bounded_output_metadata_not_output_body(tmp_path: Path, monkeypatch):
    """Output bytes are bounded and output bodies/secrets are not embedded in result."""
    project_root = create_sample_project(tmp_path)

    # 2 MB of output
    big_stdout = b"x" * (2 * 1024 * 1024)
    big_stderr = b"y" * 500

    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0

        def communicate(self, timeout=None):
            return (big_stdout, big_stderr)

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    spec = CapabilityCheckSpec(target="worker", capability=CapabilityName.TEST_FULL)
    res = execute_capability(project_root, spec)

    assert res.ok is True
    assert res.status == "succeeded"
    assert res.exit_code == 0
    assert res.stdout_bytes == len(big_stdout)
    assert res.stderr_bytes == len(big_stderr)
    assert res.output_truncated is False

    # Verify no raw stdout/stderr payload exists in model fields
    res_dict = res.model_dump()
    assert "stdout" not in res_dict
    assert "stderr" not in res_dict
    assert "output" not in res_dict
