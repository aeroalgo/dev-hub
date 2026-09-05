"""Tests for doctor workflow-pack checks and CLI entrypoint (T-HUB-052: TM-001..TM-004)."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
import pytest
import yaml

from loop.doctor.checks.workflow_pack import check_workflow_pack, run_doctor_workflow_pack
from loop.context_loop import main


def test_doctor_ok() -> None:
    """TM-001 / SC-001 / AC+ #1: doctor workflow-pack passes on dev-hub root."""
    codes = check_workflow_pack()
    assert codes == []
    exit_code = run_doctor_workflow_pack()
    assert exit_code == 0


def test_invalid_pack_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-001 / TM-002 / SC-002 / AC- #2: doctor fails on unknown pack_id (fail-closed exit 1)."""
    monkeypatch.setenv("WORKFLOW_PACK", "non-existent-pack")
    codes = check_workflow_pack(cwd=tmp_path)
    assert len(codes) >= 1
    assert "invalid_workflow_pack" in codes
    assert run_doctor_workflow_pack(cwd=tmp_path) == 1


def test_resolver_exception_fails_closed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Unexpected resolver errors produce a diagnostic and JSON exit 1."""
    def raise_error(**_: object) -> object:
        raise RuntimeError("resolver failed")

    monkeypatch.setattr("loop.doctor.checks.workflow_pack.resolve_workflow_pack", raise_error)

    assert check_workflow_pack() == ["workflow_pack_check_error"]
    assert run_doctor_workflow_pack() == 1
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "ok": False,
        "pack_id": "",
        "diagnostic_codes": ["workflow_pack_check_error"],
    }


def test_missing_rules_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-002: rules_root directory missing -> pack_rules_missing diagnostic."""
    monkeypatch.delenv("WORKFLOW_PACK", raising=False)
    monkeypatch.delenv("EPIC_WORKFLOW_PACK", raising=False)

    # Set up memory-bank and phase_registry, but NO rules_root (.cursor/rules)
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("schema: loop-phase-registry/v1\nphases: {}\n", encoding="utf-8")

    codes = check_workflow_pack(cwd=tmp_path)
    assert "pack_rules_missing" in codes
    assert run_doctor_workflow_pack(cwd=tmp_path) == 1


def test_missing_phase_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-003: phase_registry file missing -> pack_phase_registry_missing diagnostic."""
    monkeypatch.delenv("WORKFLOW_PACK", raising=False)
    monkeypatch.delenv("EPIC_WORKFLOW_PACK", raising=False)

    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cursor" / "rules").mkdir(parents=True, exist_ok=True)

    codes = check_workflow_pack(cwd=tmp_path)
    assert "pack_phase_registry_missing" in codes
    assert run_doctor_workflow_pack(cwd=tmp_path) == 1


def test_mb_root_not_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TM-004: mb_root is not writable -> mb_root_not_writable diagnostic."""
    monkeypatch.delenv("WORKFLOW_PACK", raising=False)
    monkeypatch.delenv("EPIC_WORKFLOW_PACK", raising=False)

    mb_dir = tmp_path / "memory-bank"
    mb_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cursor" / "rules").mkdir(parents=True, exist_ok=True)
    phase_reg = tmp_path / "loop" / "schemas" / "phase_registry.yaml"
    phase_reg.parent.mkdir(parents=True, exist_ok=True)
    phase_reg.write_text("schema: loop-phase-registry/v1\nphases: {}\n", encoding="utf-8")

    # Remove write permissions on memory-bank
    current_mode = os.stat(mb_dir).st_mode
    os.chmod(mb_dir, current_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    try:
        codes = check_workflow_pack(cwd=tmp_path)
        assert "mb_root_not_writable" in codes
        assert run_doctor_workflow_pack(cwd=tmp_path) == 1
    finally:
        os.chmod(mb_dir, current_mode)


def test_cli_context_loop_doctor_workflow_pack() -> None:
    """CLI integration: context_loop.py doctor workflow-pack exits 0 on valid environment."""
    exit_code = main(["--cwd", str(Path.cwd()), "doctor", "workflow-pack"])
    assert exit_code == 0
