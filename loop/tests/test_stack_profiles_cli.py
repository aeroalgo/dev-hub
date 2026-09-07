"""Unit tests for JSON CLI python -m loop.stack_profiles."""

import json
from pathlib import Path
import pytest
from loop.stack_profiles.__main__ import main


def test_cli_resolve_success(tmp_path: Path, capsys):
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ndefault_target: core\ntargets:\n  core:\n    root: .\n    profile: python\n",
        encoding="utf-8",
    )
    code = main(["resolve", "--project-root", str(tmp_path), "--capability", "test.full"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["target"] == "core"
    assert data["profile"] == "python"
    assert data["capability"] == "test.full"
    assert isinstance(data["argv"], list)
    assert "command" not in data
    assert "shell" not in data


def test_cli_resolve_missing_manifest_exit_2(tmp_path: Path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    code = main(["resolve", "--project-root", str(empty_dir), "--capability", "test.full"])
    assert code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert data["argv"] == []
    assert any(d["code"] == "project_manifest_missing" for d in data["diagnostics"])


def test_cli_resolve_js_ambiguous_exit_2(tmp_path: Path, capsys):
    js_dir = tmp_path / "js_project"
    js_dir.mkdir()
    manifest_file = js_dir / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ndefault_target: frontend\ntargets:\n  frontend:\n    root: .\n    profile: javascript\n",
        encoding="utf-8",
    )
    (js_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (js_dir / "yarn.lock").write_text("", encoding="utf-8")

    code = main(["resolve", "--project-root", str(js_dir), "--capability", "test.full"])
    assert code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert data["argv"] == []
    assert any(d["code"] == "js_package_manager_ambiguous" for d in data["diagnostics"])


def test_cli_doctor_success(tmp_path: Path, capsys):
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ntargets:\n  backend:\n    root: .\n    profile: python\n",
        encoding="utf-8",
    )
    code = main(["doctor", "--project-root", str(tmp_path)])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["schema"] == "doctor-report/v1"
    assert data["ok"] is True
    assert len(data["checks"]) > 0


def test_cli_doctor_missing_tool_exit_3(tmp_path: Path, monkeypatch, capsys):
    empty_bin_dir = tmp_path / "empty_bin"
    empty_bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin_dir))

    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ntargets:\n  backend:\n    root: .\n    profile: rust\n",
        encoding="utf-8",
    )
    code = main(["doctor", "--project-root", str(tmp_path)])
    assert code == 3
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert any(d["code"] == "tool_missing" for d in data["diagnostics"])


def test_cli_doctor_probe_failed_exit_3(tmp_path: Path, monkeypatch, capsys):
    fake_bin_dir = tmp_path / "fake_bin"
    fake_bin_dir.mkdir()
    cargo_script = fake_bin_dir / "cargo"
    cargo_script.write_text("#!/bin/sh\n/bin/sleep 10\nexit 0\n", encoding="utf-8")
    cargo_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin_dir}:/bin:/usr/bin")
    from loop.stack_profiles import doctor
    monkeypatch.setattr(doctor, "DOCTOR_PROBE_TIMEOUT_SECONDS", 1)

    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ntargets:\n  backend:\n    root: .\n    profile: rust\n",
        encoding="utf-8",
    )
    code = main(["doctor", "--project-root", str(tmp_path)])
    assert code == 3
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert any(d["code"] == "tool_probe_failed" for d in data["diagnostics"])


def test_cli_resolve_target_selector_and_json_keys(tmp_path: Path, capsys):
    """US-005 / AC+5 / NFR-4: resolve CLI JSON equals resolve_capability fields."""
    manifest_file = tmp_path / "dev-hub.project.yaml"
    manifest_file.write_text(
        "schema: dev-hub-project/v1\ntargets:\n  core:\n    root: .\n    profile: python\n",
        encoding="utf-8",
    )
    code = main([
        "resolve",
        "--project-root", str(tmp_path),
        "--target", "core",
        "--capability", "test.targeted",
        "--selector", "tests/test_cli.py::test_foo",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    expected_keys = {
        "schema", "ok", "target", "profile", "capability", "cwd", "argv",
        "timeout_seconds", "requirements", "diagnostics"
    }
    assert expected_keys.issubset(set(data.keys()))
    assert data["argv"] == ["python", "-m", "pytest", "tests/test_cli.py::test_foo"]

