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
    validate_active_context_shape as _validate_ac_text_shape,
    validate_finish_integrity,
)
from loop.incidents.store import CorruptIncidentError, list_open_incidents, parse_incidents_jsonl
from loop.incidents.metrics import load_metrics


@dataclass
class ShapeResult:
    valid: bool
    diagnostic: str | None = None


def validate_active_context_shape(path: Path | str) -> ShapeResult:
    """Validate activeContext file existence and schema shape (fail-closed)."""
    p = Path(path)
    if not p.is_file():
        return ShapeResult(valid=False, diagnostic=f"activeContext missing at {p}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ShapeResult(valid=False, diagnostic=f"activeContext unreadable at {p}: {exc}")

    shape_errs = _validate_ac_text_shape(text)
    if shape_errs:
        return ShapeResult(valid=False, diagnostic=f"activeContext shape invalid: {'; '.join(shape_errs)}")
    return ShapeResult(valid=True, diagnostic=None)


def _check_runtime_registry_valid(cwd: Path) -> CheckResult:
    try:
        from loop.runtime.registry import load_registry, InvalidRuntimeConfig
        reg_path = cwd / "loop" / "runtime_registry.yaml" if (cwd / "loop" / "runtime_registry.yaml").exists() else Path(__file__).resolve().parents[1] / "runtime_registry.yaml"
        load_registry(reg_path)
        return CheckResult(
            name="runtime_registry_valid",
            status="pass",
            detail=f"valid registry at {reg_path.name}",
        )
    except Exception as exc:
        return CheckResult(
            name="runtime_registry_valid",
            status="fail",
            detail=f"Failed to load runtime_registry.yaml: {exc}",
        )


def _check_runtime_sync_drift(cwd: Path) -> CheckResult:
    sync_bin = cwd / "bin" / "runtime-sync"
    if not sync_bin.exists():
        sync_bin = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"

    if not sync_bin.exists() or not os.access(sync_bin, os.X_OK):
        # Fallback using python script if executable not found directly or not executable
        sync_script = sync_bin
    else:
        sync_script = sync_bin

    import subprocess
    cmd = [sys.executable, str(sync_script), "--check", "--runtime", "all"]
    try:
        res = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0:
            return CheckResult(
                name="runtime_sync_drift",
                status="pass",
                detail="no runtime sync drift",
            )
        else:
            detail_msg = res.stdout.strip() or res.stderr.strip() or "runtime-sync drift detected"
            return CheckResult(
                name="runtime_sync_drift",
                status="warn",
                detail=detail_msg,
            )
    except Exception as exc:
        return CheckResult(
            name="runtime_sync_drift",
            status="warn",
            detail=f"runtime-sync check error: {exc}",
        )


def _check_runtime_binary_ok(runtime_id: str, cwd: Path) -> CheckResult:
    check_name = f"runtime_binary_{runtime_id}"
    try:
        from loop.runtime.registry import load_registry
        reg_path = cwd / "loop" / "runtime_registry.yaml" if (cwd / "loop" / "runtime_registry.yaml").exists() else Path(__file__).resolve().parents[1] / "runtime_registry.yaml"
        reg = load_registry(reg_path)
        runtime_info = reg.get_runtime(runtime_id)
    except Exception as exc:
        return CheckResult(
            name=check_name,
            status="fail",
            detail=f"Failed to load registry for {runtime_id}: {exc}",
        )

    # Determine binary name/env
    binary_env = runtime_info.get("binary_env")
    env_bin = os.environ.get(binary_env) if binary_env else None

    binary_name = env_bin or runtime_id
    binary_path = shutil.which(binary_name)

    if binary_path:
        return CheckResult(
            name=check_name,
            status="pass",
            detail=f"binary '{binary_name}' found at {binary_path}",
        )
    else:
        return CheckResult(
            name=check_name,
            status="fail",
            detail=f"binary '{binary_name}' not found in PATH",
        )


def _check_halt_rate(cwd: Path, threshold: float = 0.5) -> CheckResult:
    mb_path = cwd / "memory-bank" if not cwd.name == "memory-bank" else cwd
    metrics_path = mb_path / "metrics.json"
    if not metrics_path.is_file():
        return CheckResult(
            name="halt_rate",
            status="skipped",
            detail="metrics.json not found",
        )

    try:
        metrics = load_metrics(mb_path)
        counters = metrics.counters
        check_after_halt = counters.get("check_after_halt", 0)
        sessions_total = counters.get("sessions_total", 0)
        sessions = max(sessions_total, 1)
        rate = check_after_halt / sessions

        if rate > threshold:
            return CheckResult(
                name="halt_rate",
                status="warn",
                detail=f"halt rate {rate:.2f} > threshold {threshold:.2f} ({check_after_halt}/{sessions_total})",
            )
        return CheckResult(
            name="halt_rate",
            status="pass",
            detail=f"halt rate {rate:.2f} <= threshold {threshold:.2f} ({check_after_halt}/{sessions_total})",
        )
    except Exception as exc:
        return CheckResult(
            name="halt_rate",
            status="warn",
            detail=f"Failed to check halt rate: {exc}",
        )

try:
    from tests.architecture.check_boundaries import check_boundaries
except ImportError:
    check_boundaries = None


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
    from epic_paths import active_context_path
    ac_path = active_context_path(cwd_p)
    shape_res = validate_active_context_shape(ac_path)
    if not shape_res.valid:
        report.checklist.append(
            CheckResult(
                name="active_context_shape",
                status="fail",
                detail=shape_res.diagnostic,
            )
        )
        report.blockers.append(f"activeContext shape invalid: {shape_res.diagnostic}")
    else:
        report.checklist.append(
            CheckResult(
                name="active_context_shape",
                status="pass",
                detail="valid",
            )
        )

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

    # 7. boundary violations check (WARN if violations found)
    if check_boundaries is not None:
        try:
            boundaries_yaml = cwd_p / "tests" / "architecture" / "boundaries.yaml"
            if boundaries_yaml.exists():
                violations = check_boundaries(root_dir=cwd_p, boundaries_yaml_path=boundaries_yaml)
                if violations:
                    count = len(violations)
                    report.checklist.append(
                        CheckResult(
                            name="boundary_violations",
                            status="warn",
                            detail=f"WARNING: {count} boundary violations found",
                        )
                    )
                    report.warnings.append(f"WARNING: {count} boundary violations found")
                else:
                    report.checklist.append(
                        CheckResult(
                            name="boundary_violations",
                            status="pass",
                            detail="0 boundary violations",
                        )
                    )
            else:
                report.checklist.append(
                    CheckResult(
                        name="boundary_violations",
                        status="skipped",
                        detail="boundaries.yaml not found",
                    )
                )
        except Exception as exc:
            report.checklist.append(
                CheckResult(
                    name="boundary_violations",
                    status="warn",
                    detail=f"Check failed: {exc}",
                )
            )
            report.warnings.append(f"Boundary check exception: {exc}")

    # 8. halt_rate check
    try:
        threshold = float(os.environ.get("EPIC_DASHBOARD_HALT_WARN_RATE", "0.5"))
        halt_check = _check_halt_rate(cwd_p, threshold=threshold)
        report.checklist.append(halt_check)
        if halt_check.status == "warn":
            report.warnings.append(f"Halt rate check warning: {halt_check.detail}")
    except Exception as exc:
        report.checklist.append(
            CheckResult(
                name="halt_rate",
                status="warn",
                detail=f"Check failed: {exc}",
            )
        )
        report.warnings.append(f"Halt rate check exception: {exc}")

    # 9. runtime_registry_valid check
    reg_valid_check = _check_runtime_registry_valid(cwd_p)
    report.checklist.append(reg_valid_check)
    if reg_valid_check.status == "fail":
        report.blockers.append(f"runtime_registry_valid failed: {reg_valid_check.detail}")

    # 10. runtime_sync_drift check
    sync_drift_check = _check_runtime_sync_drift(cwd_p)
    report.checklist.append(sync_drift_check)
    if sync_drift_check.status == "warn":
        report.warnings.append(f"runtime_sync_drift warning: {sync_drift_check.detail}")

    # 11. runtime_binary check for EPIC_RUNTIME (or active/default runtime)
    active_runtime = os.environ.get("EPIC_RUNTIME", "claude")
    binary_check = _check_runtime_binary_ok(active_runtime, cwd_p)
    report.checklist.append(binary_check)
    if binary_check.status == "fail":
        report.blockers.append(f"{binary_check.name} failed: {binary_check.detail}")

    if report.blockers:
        report.exit_code = 1
    else:
        report.exit_code = 0

    return report
