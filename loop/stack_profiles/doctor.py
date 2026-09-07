"""Doctor inspection for project targets and stack profiles."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import List, Optional, Set

from loop.stack_profiles.registry import get_bundled_registry
from loop.stack_profiles.resolver import load_project_manifest
from loop.stack_profiles.schemas import (
    Diagnostic,
    DoctorCheckResult,
    DoctorReport,
    JsPackageManager,
    JsTargetSpec,
    ProjectManifest,
    validate_workspace_containment,
)

DOCTOR_PROBE_TIMEOUT_SECONDS = 5


def _probe_executable(exe_name: str, timeout: int = DOCTOR_PROBE_TIMEOUT_SECONDS) -> tuple[bool, str]:
    """Probe executable availability with --version under fixed short timeout."""
    exe_path = shutil.which(exe_name)
    if not exe_path:
        return False, f"Executable '{exe_name}' not found in PATH"

    try:
        proc = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode == 0:
            version_out = (proc.stdout or proc.stderr or "").strip().splitlines()
            ver_str = version_out[0] if version_out else "available"
            return True, ver_str
        return False, f"'{exe_name} --version' exited with code {proc.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"'{exe_name} --version' timed out after {timeout}s"
    except Exception as err:
        return False, f"Failed to execute '{exe_name} --version': {err}"


def doctor_project_profiles(project_root: Path, *, target: Optional[str] = None) -> DoctorReport:
    """Inspect project manifest and tool availability without executing project scripts."""
    checks: List[DoctorCheckResult] = []
    diagnostics: List[Diagnostic] = []

    try:
        manifest, diag = load_project_manifest(project_root)
    except Exception as err:
        diagnostics.append(
            Diagnostic(
                code="project_manifest_invalid",
                message=f"Failed to load project manifest: {err}",
            )
        )
        return DoctorReport(ok=False, checks=checks, diagnostics=diagnostics)

    if diag or not manifest:
        if diag:
            diagnostics.append(diag)
        return DoctorReport(ok=False, checks=checks, diagnostics=diagnostics)

    proj_manifest = manifest
    registry = get_bundled_registry()

    if target and target not in proj_manifest.targets:
        diagnostics.append(
            Diagnostic(
                code="target_unknown",
                message=f"Target '{target}' not found in project manifest",
                target=target,
            )
        )
        return DoctorReport(ok=False, checks=checks, diagnostics=diagnostics)

    targets_to_check = [target] if target else list(proj_manifest.targets.keys())

    for tgt_name in targets_to_check:
        tgt_spec = proj_manifest.targets[tgt_name]

        # 1. Target root containment and existence check
        try:
            target_dir = validate_workspace_containment(project_root, tgt_spec.root)
            if not target_dir.exists():
                checks.append(
                    DoctorCheckResult(
                        name="target_root",
                        target=tgt_name,
                        status="fail",
                        message=f"Target root directory does not exist: {target_dir}",
                    )
                )
                diagnostics.append(
                    Diagnostic(
                        code="target_root_missing",
                        message=f"Target root '{tgt_spec.root}' does not exist",
                        target=tgt_name,
                    )
                )
                continue
            elif not target_dir.is_dir():
                checks.append(
                    DoctorCheckResult(
                        name="target_root",
                        target=tgt_name,
                        status="fail",
                        message=f"Target root is not a directory: {target_dir}",
                    )
                )
                diagnostics.append(
                    Diagnostic(
                        code="target_root_unsafe",
                        message=f"Target root '{tgt_spec.root}' is not a directory",
                        target=tgt_name,
                    )
                )
                continue
            else:
                checks.append(
                    DoctorCheckResult(
                        name="target_root",
                        target=tgt_name,
                        status="pass",
                        message=f"Target root valid: {tgt_spec.root}",
                    )
                )
        except ValueError as err:
            checks.append(
                DoctorCheckResult(
                    name="target_root",
                    target=tgt_name,
                    status="fail",
                    message=str(err),
                )
            )
            diagnostics.append(
                Diagnostic(
                    code="target_root_unsafe",
                    message=str(err),
                    target=tgt_name,
                )
            )
            continue

        # 2. Profile existence and required executables
        profile_def = registry.profiles.get(tgt_spec.profile)
        if not profile_def:
            checks.append(
                DoctorCheckResult(
                    name="profile_lookup",
                    target=tgt_name,
                    status="fail",
                    message=f"Profile '{tgt_spec.profile}' not found in registry",
                )
            )
            diagnostics.append(
                Diagnostic(
                    code="profile_unknown",
                    message=f"Profile '{tgt_spec.profile}' not in registry",
                    target=tgt_name,
                )
            )
            continue

        required_tools: Set[str] = set(profile_def.required_executables)

        # For JS targets, determine manager and check lockfiles
        if isinstance(tgt_spec, JsTargetSpec):
            js_manager = tgt_spec.package_manager
            if not js_manager:
                found_managers: List[str] = []
                lockfile_map = {
                    "package-lock.json": "npm",
                    "pnpm-lock.yaml": "pnpm",
                    "yarn.lock": "yarn",
                    "bun.lockb": "bun",
                    "bun.lock": "bun",
                }
                for lf_name, mgr in lockfile_map.items():
                    if (target_dir / lf_name).is_file() and mgr not in found_managers:
                        found_managers.append(mgr)

                if len(found_managers) == 1:
                    js_manager = found_managers[0]
                elif len(found_managers) > 1:
                    mgr_list = ", ".join(found_managers)
                    checks.append(
                        DoctorCheckResult(
                            name="js_lockfile",
                            target=tgt_name,
                            status="fail",
                            message=f"Ambiguous JS package managers detected ({mgr_list})",
                        )
                    )
                    diagnostics.append(
                        Diagnostic(
                            code="js_package_manager_ambiguous",
                            message=f"Ambiguous JS package managers ({mgr_list}); explicit package_manager required",
                            target=tgt_name,
                        )
                    )
                else:
                    checks.append(
                        DoctorCheckResult(
                            name="js_lockfile",
                            target=tgt_name,
                            status="fail",
                            message=f"No JS lockfile found in {tgt_spec.root} and no package_manager configured",
                        )
                    )
                    diagnostics.append(
                        Diagnostic(
                            code="js_package_manager_missing",
                            message=f"No lockfile or explicit package_manager for target '{tgt_name}'",
                            target=tgt_name,
                        )
                    )

            if js_manager:
                required_tools.add(js_manager)

        # 3. Probe required executables
        for tool in sorted(required_tools):
            ok, msg = _probe_executable(tool, timeout=DOCTOR_PROBE_TIMEOUT_SECONDS)
            if ok:
                checks.append(
                    DoctorCheckResult(
                        name=f"tool:{tool}",
                        target=tgt_name,
                        status="pass",
                        message=f"Tool '{tool}' available",
                        detail=msg,
                    )
                )
            else:
                checks.append(
                    DoctorCheckResult(
                        name=f"tool:{tool}",
                        target=tgt_name,
                        status="fail",
                        message=f"Tool '{tool}' unavailable or probe failed",
                        detail=msg,
                    )
                )
                diagnostics.append(
                    Diagnostic(
                        code="tool_probe_failed" if "timed out" in msg or "exited with code" in msg else "tool_missing",
                        message=f"Required tool '{tool}' check failed: {msg}",
                        target=tgt_name,
                    )
                )

    all_ok = len(diagnostics) == 0 and all(c.status != "fail" for c in checks)
    return DoctorReport(ok=all_ok, checks=checks, diagnostics=diagnostics)
