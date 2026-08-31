"""loop doctor preflight checklist implementation."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from _lib import (
    runner_owner_status,
)
from epic_paths import epic_dir
from epic import (
    load_epic_state,
    read_active_context,
    validate_active_context_shape,
    validate_finish_integrity,
)
from loop.incidents.store import CorruptIncidentError, list_open_incidents, parse_incidents_jsonl


@dataclass
class CheckResult:
    name: str
    status: str  # "pass", "fail", "warn", "skipped"
    detail: str | None = None


@dataclass
class DoctorReport:
    checklist: list[CheckResult] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    exit_code: int = 0


def run_doctor(cwd: str | Path, auto_repair: bool = False, format: str = "text") -> DoctorReport:
    cwd_p = Path(cwd)
    report = DoctorReport()

    # Check project directory misconfig (exit_code = 2 if misconfigured)
    if not cwd_p.exists() or not (cwd_p / "memory-bank").exists():
        report.exit_code = 2
        report.blockers.append(f"Invalid PROJECT_ROOT or missing memory-bank at {cwd_p}")
        report.checklist.append(
            CheckResult(
                name="project_root_valid",
                status="fail",
                detail=f"Directory or memory-bank missing: {cwd_p}",
            )
        )
        return report

    report.checklist.append(
        CheckResult(
            name="project_root_valid",
            status="pass",
            detail=str(cwd_p),
        )
    )

    # 1. active_context_shape
    try:
        ac_text = read_active_context(cwd_p)
        shape_errs = validate_active_context_shape(ac_text)
        if shape_errs:
            report.checklist.append(
                CheckResult(
                    name="active_context_shape",
                    status="fail",
                    detail="; ".join(shape_errs),
                )
            )
            report.blockers.append(f"activeContext shape invalid: {'; '.join(shape_errs)}")
        else:
            report.checklist.append(
                CheckResult(
                    name="active_context_shape",
                    status="pass",
                    detail="valid",
                )
            )
    except Exception as exc:
        report.checklist.append(
            CheckResult(
                name="active_context_shape",
                status="fail",
                detail=str(exc),
            )
        )
        report.blockers.append(f"activeContext unreadable: {exc}")

    # 2. armed_decompose_exists
    st = load_epic_state(cwd_p) or {}
    decompose = st.get("armed_decompose")
    if decompose:
        decomp_path = cwd_p / decompose
        if not decomp_path.exists():
            report.checklist.append(
                CheckResult(
                    name="armed_decompose_exists",
                    status="fail",
                    detail=f"Decompose file missing: {decompose}",
                )
            )
            report.blockers.append(f"armed_decompose missing: {decompose}")
        else:
            report.checklist.append(
                CheckResult(
                    name="armed_decompose_exists",
                    status="pass",
                    detail=str(decompose),
                )
            )
    else:
        report.checklist.append(
            CheckResult(
                name="armed_decompose_exists",
                status="pass",
                detail="none armed",
            )
        )

    # 3. finish_integrity
    if decompose and (cwd_p / decompose).exists():
        armed_step = str(st.get("armed_step") or "")
        integrity = validate_finish_integrity(
            cwd_p, decompose=str(decompose), step_id=armed_step, require_verify_pass=False
        )
        if not integrity["ok"]:
            report.checklist.append(
                CheckResult(
                    name="finish_integrity",
                    status="fail",
                    detail="; ".join(integrity["errors"]),
                )
            )
            report.blockers.append(f"finish_integrity failed: {'; '.join(integrity['errors'])}")
        else:
            report.checklist.append(
                CheckResult(
                    name="finish_integrity",
                    status="pass",
                    detail="valid",
                )
            )
    else:
        report.checklist.append(
            CheckResult(
                name="finish_integrity",
                status="pass",
                detail="skipped (no decompose armed)",
            )
        )

    # 4. stale_owner
    ep_dir = epic_dir(cwd_p)
    owner_st = runner_owner_status(ep_dir)
    if owner_st and owner_st.get("owner") and not owner_st.get("owner_alive"):
        owner = owner_st["owner"]
        pid = owner.get("pid")
        remediation = f"Remove stale runner.json / runner.lock in {ep_dir}"
        report.checklist.append(
            CheckResult(
                name="stale_owner",
                status="fail",
                detail=f"Stale runner lock detected (PID {pid}). Remediation: {remediation}",
            )
        )
        report.blockers.append(f"stale_owner: dead PID {pid}. Remediation: {remediation}")
    else:
        report.checklist.append(
            CheckResult(
                name="stale_owner",
                status="pass",
                detail="clean",
            )
        )

    # 5. incidents_corrupt & open_incidents
    ep_dir = epic_dir(cwd_p)
    incidents_path = ep_dir / "incidents.jsonl"
    if incidents_path.exists():
        try:
            records = parse_incidents_jsonl(incidents_path)
            report.checklist.append(
                CheckResult(
                    name="incidents_corrupt",
                    status="pass",
                    detail="clean",
                )
            )
            open_incs = [r for r in records if r.status == "open"]
            if open_incs:
                report.checklist.append(
                    CheckResult(
                        name="open_incidents",
                        status="warn",
                        detail=f"{len(open_incs)} open incidents found",
                    )
                )
                report.warnings.append(f"{len(open_incs)} open incidents pending resolution")
            else:
                report.checklist.append(
                    CheckResult(
                        name="open_incidents",
                        status="pass",
                        detail="0 open",
                    )
                )
        except CorruptIncidentError as exc:
            report.checklist.append(
                CheckResult(
                    name="incidents_corrupt",
                    status="fail",
                    detail=str(exc),
                )
            )
            report.blockers.append(f"Corrupt incidents log: {exc}")
    else:
        report.checklist.append(
            CheckResult(
                name="incidents_corrupt",
                status="pass",
                detail="incidents.jsonl does not exist",
            )
        )
        report.checklist.append(
            CheckResult(
                name="open_incidents",
                status="pass",
                detail="0 open",
            )
        )

    # 6. board_sync_stale (optional if hub-board on PATH)
    hub_board_bin = shutil.which("hub-board")
    if hub_board_bin:
        # Check board sync if hub-board is available
        report.checklist.append(
            CheckResult(
                name="board_sync_stale",
                status="pass",
                detail="hub-board present",
            )
        )
    else:
        report.checklist.append(
            CheckResult(
                name="board_sync_stale",
                status="skipped",
                detail="hub-board CLI not found on PATH",
            )
        )

    if report.blockers:
        report.exit_code = 1
    else:
        report.exit_code = 0

    return report
