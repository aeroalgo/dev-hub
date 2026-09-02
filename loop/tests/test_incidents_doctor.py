"""Tests for loop doctor CLI / run_doctor function."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_paths import epic_dir
from loop.incidents.doctor import run_doctor


def test_doctor_stale_owner_exit_one(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")
    (mb / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    ep_dir = epic_dir(tmp_path)
    runner_json = ep_dir / "runner.json"
    runner_json.write_text(json.dumps({"pid": 999999, "started_at": "2026-08-30T00:00:00Z"}), encoding="utf-8")

    report = run_doctor(tmp_path)
    assert report.exit_code == 1
    stale_chk = next(c for c in report.checklist if c.name == "stale_owner")
    assert stale_chk.status == "fail"
    assert "Remediation:" in stale_chk.detail
    assert any("stale_owner" in b for b in report.blockers)


def test_doctor_valid_project_exit_zero(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")
    (mb / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    report = run_doctor(tmp_path)
    assert report.exit_code == 0
    assert not report.blockers


def test_doctor_misconfig_exit_two(tmp_path: Path) -> None:
    non_existent = tmp_path / "non_existent_dir"
    report = run_doctor(non_existent)
    assert report.exit_code == 2
    assert report.blockers


def test_doctor_corrupt_incidents_blocker(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")

    ep_dir = epic_dir(tmp_path)
    incidents_file = ep_dir / "incidents.jsonl"
    incidents_file.write_text("INVALID JSON LINE\n", encoding="utf-8")

    report = run_doctor(tmp_path)
    assert report.exit_code == 1
    chk = next(c for c in report.checklist if c.name == "incidents_corrupt")
    assert chk.status == "fail"
    assert any("Corrupt incidents log" in b for b in report.blockers)


def test_doctor_open_incidents_warn_only(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")

    ep_dir = epic_dir(tmp_path)
    incidents_file = ep_dir / "incidents.jsonl"
    rec = {
        "incident_id": "inc-1",
        "project_root": str(tmp_path),
        "epic_id": "T-HUB-017",
        "step_id": "s07",
        "phase": "IMPLEMENT",
        "session_id": "sess-1",
        "source": "check_after",
        "diagnostic_codes": ["stale_owner"],
        "fingerprint": "abc",
        "opened_at": "2026-08-30T00:00:00Z",
        "status": "open"
    }
    incidents_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

    report = run_doctor(tmp_path)
    assert report.exit_code == 0
    chk = next(c for c in report.checklist if c.name == "open_incidents")
    assert chk.status == "warn"
    assert any("open incidents pending resolution" in w for w in report.warnings)


def test_doctor_board_sync_skipped_when_cli_missing(tmp_path: Path) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")

    report = run_doctor(tmp_path)
    chk = next(c for c in report.checklist if c.name == "board_sync_stale")
    assert chk.status in ("skipped", "pass")


def test_doctor_boundary_check_warn(tmp_path: Path, monkeypatch) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")

    arch_dir = tmp_path / "tests" / "architecture"
    arch_dir.mkdir(parents=True)
    (arch_dir / "boundaries.yaml").write_text("contracts: []\n", encoding="utf-8")

    from tests.architecture.check_boundaries import Violation
    dummy_violation = Violation(
        contract_id="C001",
        file_path="loop/test.py",
        line_number=10,
        imported_module="hooks.epic",
        forbidden_pattern="hooks.*",
        reason="Forbidden import",
    )

    import loop.incidents.doctor as doctor_mod
    monkeypatch.setattr(doctor_mod, "check_boundaries", lambda root_dir, yaml_file: [dummy_violation])

    report = doctor_mod.run_doctor(tmp_path)
    assert report.exit_code == 0
    chk = next(c for c in report.checklist if c.name == "boundary_violations")
    assert chk.status == "warn"
    assert "WARNING: 1 boundary violations" in chk.detail
    assert any("boundary violations" in w for w in report.warnings)


def test_doctor_boundary_check_pass(tmp_path: Path, monkeypatch) -> None:
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\nsome_file.py\n## Handoff\nDone\n", encoding="utf-8")

    arch_dir = tmp_path / "tests" / "architecture"
    arch_dir.mkdir(parents=True)
    (arch_dir / "boundaries.yaml").write_text("contracts: []\n", encoding="utf-8")

    import loop.incidents.doctor as doctor_mod
    monkeypatch.setattr(doctor_mod, "check_boundaries", lambda root_dir, yaml_file: [])

    report = doctor_mod.run_doctor(tmp_path)
    assert report.exit_code == 0
    chk = next(c for c in report.checklist if c.name == "boundary_violations")
    assert chk.status == "pass"
    assert "0 boundary violations" in chk.detail
    assert not any("boundary violations" in w for w in report.warnings)

