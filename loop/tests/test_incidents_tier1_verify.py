"""Tests for tier1 verification of orchestration invariants."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from loop.incidents.schema import IncidentRecord
from loop.incidents.tier1_verify import VerifyResult, build_verify_ac_slice, run_tier1_verify


def _make_sample_incident(incident_id: str, diag_codes: list[str]) -> IncidentRecord:
    return IncidentRecord.model_validate({
        "schema": "loop-incident/v1",
        "incident_id": incident_id,
        "opened_at": "2026-08-30T10:00:00Z",
        "project_root": "/home/aero/PyProject/dev-hub",
        "epic_id": "T-HUB-018",
        "step_id": "s05",
        "phase": "BACK IMPLEMENT",
        "session_id": "sess-123",
        "source": "tier1_verify_test",
        "status": "open",
        "diagnostic_codes": diag_codes,
        "fingerprint": "fp-123",
    })


def test_verify_slice_contains_only_loop_tests() -> None:
    record = _make_sample_incident("INC-001", ["active_context_shape_invalid"])
    cmds = build_verify_ac_slice(record, Path("/tmp/fake_root"))
    assert len(cmds) > 0
    for cmd in cmds:
        assert "loop/tests/" in cmd
        assert "src/" not in cmd
        assert "frontend/" not in cmd


def test_ac_slice_no_product_paths() -> None:
    record = _make_sample_incident("INC-002", ["generic_error"])
    cmds = build_verify_ac_slice(record, Path("/tmp/fake_root"))
    for cmd in cmds:
        assert "loop/" in cmd
        assert "src/" not in cmd
        assert "frontend/" not in cmd


def test_verify_pass_returns_true() -> None:
    record = _make_sample_incident("INC-003", ["active_context_shape_invalid"])

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        res = run_tier1_verify(record, Path("/tmp/fake_root"))
        assert res.passed is True
        assert "Exit: 0" in res.output


def test_verify_fail_returns_false() -> None:
    record = _make_sample_incident("INC-004", ["active_context_shape_invalid"])

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="FAIL", stderr="Err")
        res = run_tier1_verify(record, Path("/tmp/fake_root"))
        assert res.passed is False


def test_pass_resolves_incident(tmp_path: Path) -> None:
    record = _make_sample_incident("INC-005", ["active_context_shape_invalid"])

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    incidents_jsonl = epic_dir / "incidents.jsonl"
    incidents_jsonl.write_text(record.model_dump_json(by_alias=True) + "\n", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        res = run_tier1_verify(record, tmp_path, epic_dir=epic_dir)
        assert res.passed is True

    content = incidents_jsonl.read_text(encoding="utf-8")
    assert '"status":"resolved"' in content or '"status": "resolved"' in content
    assert '"resolution_tier":"tier1"' in content or '"resolution_tier": "tier1"' in content


def test_verify_fail_increments_tier1_failures(tmp_path: Path) -> None:
    record = _make_sample_incident("INC-006", ["active_context_shape_invalid"])

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    incidents_jsonl = epic_dir / "incidents.jsonl"
    incidents_jsonl.write_text(record.model_dump_json(by_alias=True) + "\n", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="FAIL", stderr="Error")
        res = run_tier1_verify(record, tmp_path, epic_dir=epic_dir)
        assert res.passed is False

    content = incidents_jsonl.read_text(encoding="utf-8")
    assert '"status":"open"' in content or '"status": "open"' in content
