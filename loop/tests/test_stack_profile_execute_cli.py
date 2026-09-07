"""Unit and integration tests for JSON CLI python -m loop.stack_profiles execute."""

import json
from pathlib import Path
import subprocess
import pytest
from loop.stack_profiles.__main__ import main
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionResult,
    execute_capability,
)
from loop.stack_profiles.schemas import CapabilityName


def _setup_mock_project(tmp_path: Path) -> Path:
    """Setup a temporary project."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
targets:
  core:
    root: .
    profile: python
""",
        encoding="utf-8",
    )
    return tmp_path


def test_execute_cli_json_matches_api_success_result(tmp_path: Path, monkeypatch, capsys):
    """cp1 / TM-011: execute CLI JSON matches API success result parity."""
    project_root = _setup_mock_project(tmp_path)

    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 0

        def communicate(self, timeout=None):
            return (b"ok", b"")

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    # 1. Direct API call
    spec = CapabilityCheckSpec(target="core", capability=CapabilityName.TEST_FULL)
    api_res = execute_capability(project_root, spec)
    assert api_res.ok is True
    assert api_res.status == "succeeded"

    # 2. CLI call
    exit_code = main([
        "execute",
        "--project-root", str(project_root),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    cli_data = json.loads(captured.out)

    assert cli_data["schema"] == api_res.schema_version
    assert cli_data["ok"] == api_res.ok
    assert cli_data["status"] == api_res.status
    assert cli_data["target"] == api_res.target
    assert cli_data["profile"] == api_res.profile
    assert cli_data["capability"] == api_res.capability
    assert cli_data["exit_code"] == api_res.exit_code
    assert cli_data["argv"] == api_res.argv


def test_execute_cli_json_matches_api_failed_result(tmp_path: Path, monkeypatch, capsys):
    """cp1 / TM-011: execute CLI JSON matches API failed result parity."""
    project_root = _setup_mock_project(tmp_path)

    class MockProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 17

        def communicate(self, timeout=None):
            return (b"", b"failure error")

    monkeypatch.setattr(subprocess, "Popen", MockProcess)

    spec = CapabilityCheckSpec(target="core", capability=CapabilityName.TEST_FULL)
    api_res = execute_capability(project_root, spec)
    assert api_res.ok is False
    assert api_res.status == "failed"
    assert api_res.exit_code == 17

    exit_code = main([
        "execute",
        "--project-root", str(project_root),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 17
    captured = capsys.readouterr()
    cli_data = json.loads(captured.out)

    assert cli_data["ok"] is False
    assert cli_data["status"] == "failed"
    assert cli_data["exit_code"] == 17
    assert cli_data["target"] == "core"
    assert cli_data["capability"] == "test.full"


def test_execute_cli_exit_mapping(tmp_path: Path, monkeypatch, capsys):
    """cp2: Exit mapping: 0 success, 2 resolution_failed, 3 spawn_failed, 4 timed_out, child exit for failed."""
    # 1. resolution_failed -> exit 2 (missing manifest)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    exit_code = main([
        "execute",
        "--project-root", str(empty_dir),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "resolution_failed"

    # 2. spawn_failed -> exit 3
    project_root = _setup_mock_project(tmp_path / "proj")
    def _raise_oserror(*args, **kwargs):
        raise OSError("spawn error")

    monkeypatch.setattr(subprocess, "Popen", _raise_oserror)
    exit_code = main([
        "execute",
        "--project-root", str(project_root),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 3
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "spawn_failed"

    # 3. timed_out -> exit 4
    class MockTimeoutProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["python", "-m", "pytest"], timeout=timeout)

        def kill(self):
            pass

        def wait(self, timeout=None):
            self.returncode = -9
            return -9

    monkeypatch.setattr(subprocess, "Popen", MockTimeoutProcess)
    exit_code = main([
        "execute",
        "--project-root", str(project_root),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 4
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "timed_out"

    # 4. failed with non-zero exit code (e.g. 42)
    class MockFailProcess:
        def __init__(self, *args, **kwargs):
            self.returncode = 42

        def communicate(self, timeout=None):
            return (b"", b"fail 42")

    monkeypatch.setattr(subprocess, "Popen", MockFailProcess)
    exit_code = main([
        "execute",
        "--project-root", str(project_root),
        "--target", "core",
        "--capability", "test.full",
    ])
    assert exit_code == 42
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "failed"
    assert data["exit_code"] == 42
