"""Tests for the runtime-specific checks in :mod:`loop.incidents.doctor`."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from loop.incidents import doctor as doctor_mod


def test_runtime_registry_valid_pass(tmp_path: Path) -> None:
    """A valid checkout-local registry passes the registry check."""
    registry = tmp_path / "loop" / "runtime_registry.yaml"
    registry.parent.mkdir()
    registry.write_text(
        'schema_version: "runtime-registry/v1"\n'
        "runtimes:\n"
        "  codex:\n"
        "    id: codex\n"
        '    adapter_module: "loop.runtime_adapters.codex"\n',
        encoding="utf-8",
    )

    result = doctor_mod._check_runtime_registry_valid(tmp_path)

    assert result.name == "runtime_registry_valid"
    assert result.status == "pass"


def test_runtime_registry_valid_fail(tmp_path: Path) -> None:
    """An invalid checkout-local registry fails closed."""
    registry = tmp_path / "loop" / "runtime_registry.yaml"
    registry.parent.mkdir()
    registry.write_text("schema_version: invalid\n", encoding="utf-8")

    result = doctor_mod._check_runtime_registry_valid(tmp_path)

    assert result.name == "runtime_registry_valid"
    assert result.status == "fail"
    assert "Failed to load runtime_registry.yaml" in result.detail


def test_runtime_sync_drift_warn(tmp_path: Path, monkeypatch) -> None:
    """A non-zero runtime-sync check is reported as a warning."""
    sync_bin = tmp_path / "bin" / "runtime-sync"
    sync_bin.parent.mkdir()
    sync_bin.touch()
    completed = SimpleNamespace(returncode=1, stdout="Drift detected", stderr="")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return completed

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = doctor_mod._check_runtime_sync_drift(tmp_path)

    assert result.name == "runtime_sync_drift"
    assert result.status == "warn"
    assert result.detail == "Drift detected"
    assert calls[0][1]["cwd"] == tmp_path
    assert calls[0][0][0] == [doctor_mod.sys.executable, str(sync_bin), "--check", "--runtime", "all"]


def test_runtime_sync_drift_pass(tmp_path: Path, monkeypatch) -> None:
    """A zero runtime-sync exit code is reported as a pass."""
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    result = doctor_mod._check_runtime_sync_drift(tmp_path)

    assert result.name == "runtime_sync_drift"
    assert result.status == "pass"
    assert result.detail == "no runtime sync drift"


def test_runtime_binary_ok_error(tmp_path: Path, monkeypatch) -> None:
    """A missing configured runtime binary is reported as a failure."""
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda binary: None)

    result = doctor_mod._check_runtime_binary_ok("codex", tmp_path)

    assert result.name == "runtime_binary_codex"
    assert result.status == "fail"
    assert "binary 'codex' not found in PATH" == result.detail


def test_runtime_binary_ok_pass(tmp_path: Path, monkeypatch) -> None:
    """A configured runtime binary found on PATH is reported as a pass."""
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.setattr(doctor_mod.shutil, "which", lambda binary: "/usr/local/bin/codex")

    result = doctor_mod._check_runtime_binary_ok("codex", tmp_path)

    assert result.name == "runtime_binary_codex"
    assert result.status == "pass"
    assert result.detail == "binary 'codex' found at /usr/local/bin/codex"


def test_runbook_codex_pilot_exists() -> None:
    """The README-linked Codex pilot runbook remains present."""
    project_root = Path(__file__).resolve().parents[2]
    runbook = project_root / "docs" / "runbooks" / "codex-loop-pilot.md"
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    assert runbook.is_file()
    assert "[`docs/runbooks/codex-loop-pilot.md`](docs/runbooks/codex-loop-pilot.md)" in readme


def test_workflow_runtime_registry_link() -> None:
    """WORKFLOW.md points to the canonical runtime registry."""
    project_root = Path(__file__).resolve().parents[2]
    workflow = (project_root / "loop" / "WORKFLOW.md").read_text(encoding="utf-8")

    assert "[`loop/runtime_registry.yaml`](runtime_registry.yaml)" in workflow


def test_readme_no_stale_codex_message() -> None:
    """README does not claim that the Codex runtime is unsupported."""
    project_root = Path(__file__).resolve().parents[2]
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    assert "не запускает Codex" not in readme
