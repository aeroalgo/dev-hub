"""Tests for doctor_project_profiles."""

import os
from pathlib import Path
import pytest
from loop.stack_profiles.doctor import doctor_project_profiles
from loop.stack_profiles.schemas import DiagnosticCode


def test_doctor_missing_manifest(tmp_path: Path):
    report = doctor_project_profiles(tmp_path)
    assert not report.ok
    assert any(d.code == "project_manifest_missing" for d in report.diagnostics)


def test_doctor_unknown_target(tmp_path: Path):
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text("schema: dev-hub-project/v1\ntargets:\n  web:\n    root: .\n    profile: python\n", encoding="utf-8")
    report = doctor_project_profiles(tmp_path, target="backend")
    assert not report.ok
    assert any(d.code == "target_unknown" for d in report.diagnostics)


def test_doctor_fake_executable_probes_version_only_and_no_scripts(tmp_path: Path, monkeypatch):
    """US-006 / TM-010 / SC-006 / FR-012 / NFR-6:
    Fake executable records invoked argv. Must only contain --version, never test/build/script names.
    """
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()
    log_file = tmp_path / "exe_calls.log"

    # Create a fake python, fake cargo, fake npm
    for exe in ("python", "cargo", "npm"):
        script = fake_bin_dir / exe
        script.write_text(
            f"#!/bin/sh\necho \"$@\" >> '{log_file}'\necho '{exe} 1.0.0'\nexit 0\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin_dir}:{os.environ.get('PATH', '')}")

    proj_dir = tmp_path / "project"
    proj_dir.mkdir()
    (proj_dir / "services" / "app").mkdir(parents=True)
    (proj_dir / "frontend").mkdir(parents=True)
    (proj_dir / "frontend" / "package-lock.json").write_text("{}", encoding="utf-8")

    manifest = proj_dir / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
targets:
  app:
    root: services/app
    profile: python
  web:
    root: frontend
    profile: javascript
""",
        encoding="utf-8",
    )

    report = doctor_project_profiles(proj_dir)
    assert report.ok is True
    assert len(report.checks) > 0

    # Inspect call log
    if log_file.exists():
        calls = log_file.read_text(encoding="utf-8").strip().splitlines()
        for call in calls:
            assert call == "--version", f"Fake executable called with forbidden args: {call}"
            # Ensure no application scripts or test runner commands are executed
            assert "pytest" not in call
            assert "test" not in call
            assert "build" not in call
            assert "run" not in call


def test_doctor_missing_tool_exit_diagnostic(tmp_path: Path, monkeypatch):
    """Missing tool emits tool_missing diagnostic."""
    empty_bin_dir = tmp_path / "empty_bin"
    empty_bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin_dir))

    proj_dir = tmp_path / "project"
    proj_dir.mkdir()
    (proj_dir / "services" / "app").mkdir(parents=True)

    manifest = proj_dir / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
targets:
  app:
    root: services/app
    profile: rust
""",
        encoding="utf-8",
    )

    report = doctor_project_profiles(proj_dir)
    assert report.ok is False
    assert any(d.code == "tool_missing" for d in report.diagnostics)


def test_doctor_probe_timeout_exit_diagnostic(tmp_path: Path, monkeypatch):
    """Probe timeout emits tool_probe_failed diagnostic."""
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()

    # Create a hanging cargo executable
    cargo_script = fake_bin_dir / "cargo"
    cargo_script.write_text("#!/bin/sh\n/bin/sleep 10\nexit 0\n", encoding="utf-8")
    cargo_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin_dir}:/bin:/usr/bin")

    # Set doctor probe timeout to 1s for test
    from loop.stack_profiles import doctor
    monkeypatch.setattr(doctor, "DOCTOR_PROBE_TIMEOUT_SECONDS", 1)

    proj_dir = tmp_path / "project"
    proj_dir.mkdir()
    (proj_dir / "services" / "app").mkdir(parents=True)

    manifest = proj_dir / "dev-hub.project.yaml"
    manifest.write_text(
        """schema: dev-hub-project/v1
targets:
  app:
    root: services/app
    profile: rust
""",
        encoding="utf-8",
    )

    report = doctor.doctor_project_profiles(proj_dir)
    assert report.ok is False
    assert any(d.code == "tool_probe_failed" for d in report.diagnostics)

