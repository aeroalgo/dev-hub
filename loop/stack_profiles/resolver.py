"""Pure capability resolver for project targets and stack profiles."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import yaml
from pydantic import ValidationError

from loop.stack_profiles.registry import get_bundled_registry
from loop.stack_profiles.schemas import (
    CapabilityName,
    CapabilityRequest,
    CapabilityResolution,
    Diagnostic,
    DiagnosticCode,
    JsPackageManager,
    JsTargetSpec,
    ProjectManifest,
    TargetSpec,
    validate_workspace_containment,
)

MANIFEST_FILENAME = "dev-hub.project.yaml"

JS_LOCKFILES = {
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}


def load_project_manifest(project_root: Path) -> Tuple[Optional[ProjectManifest], Optional[Diagnostic]]:
    """Load and validate dev-hub.project.yaml from the project root strictly (no parent/child walking)."""
    manifest_path = project_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None, Diagnostic(
            code="project_manifest_missing",
            message=f"Project manifest not found at {manifest_path}",
        )

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as err:
        return None, Diagnostic(
            code="project_manifest_invalid",
            message=f"Failed to parse YAML from {manifest_path}: {err}",
        )

    if not isinstance(raw_data, dict):
        return None, Diagnostic(
            code="project_manifest_invalid",
            message=f"Project manifest root must be a mapping/dict, got {type(raw_data).__name__}",
        )

    try:
        manifest = ProjectManifest.model_validate(raw_data)
        return manifest, None
    except ValidationError as err:
        return None, Diagnostic(
            code="project_manifest_invalid",
            message=f"Project manifest validation failed: {err}",
        )


def _detect_js_package_manager(
    target_dir: Path, target_spec: JsTargetSpec
) -> Tuple[Optional[str], Optional[Diagnostic]]:
    """Determine the JS package manager via explicit override or exact single lockfile discovery."""
    if target_spec.package_manager:
        return target_spec.package_manager, None

    found_managers = set()
    found_files = []

    # Check known lockfiles
    for filename, manager in JS_LOCKFILES.items():
        if (target_dir / filename).is_file():
            found_managers.add(manager)
            found_files.append(filename)

    # Note: bun.lock and bun.lockb both map to "bun". If both are present, found_managers length is 1.
    if len(found_managers) == 0:
        return None, Diagnostic(
            code="js_package_manager_missing",
            message=f"No supported JS lockfile found in {target_dir} and no package_manager override provided",
        )
    if len(found_managers) > 1:
        return None, Diagnostic(
            code="js_package_manager_ambiguous",
            message=f"Ambiguous JS package managers detected ({', '.join(sorted(found_managers))}) from lockfiles: {', '.join(sorted(found_files))}",
        )

    return next(iter(found_managers)), None


def resolve_capability(
    project_root: Path,
    capability: CapabilityRequest | str,
    *,
    target: Optional[str] = None,
    selector: Optional[str] = None,
) -> CapabilityResolution:
    """Resolve structured argv, cwd, and diagnostics for a capability on a project target."""
    if isinstance(capability, CapabilityRequest):
        req_cap: str = str(capability.capability)
        target = capability.target or target
        selector = capability.selector or selector
    else:
        req_cap = str(capability)

    # 1. Load Manifest
    manifest, diag = load_project_manifest(project_root)
    if diag or not manifest:
        return CapabilityResolution(
            ok=False,
            capability=req_cap,
            diagnostics=[diag] if diag else [],
        )

    # 2. Target Selection
    selected_target_name = target or manifest.default_target
    if not selected_target_name:
        return CapabilityResolution(
            ok=False,
            capability=req_cap,
            diagnostics=[
                Diagnostic(
                    code="target_selection_required",
                    message="Target name not provided and default_target is not configured in manifest",
                )
            ],
        )

    if selected_target_name not in manifest.targets:
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            capability=req_cap,
            diagnostics=[
                Diagnostic(
                    code="target_unknown",
                    message=f"Target '{selected_target_name}' not found in manifest targets: {list(manifest.targets.keys())}",
                )
            ],
        )

    target_spec: TargetSpec = manifest.targets[selected_target_name]

    # 3. Target Root Containment & Existence
    try:
        resolved_cwd = validate_workspace_containment(project_root, target_spec.root)
    except ValueError as err:
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            profile=target_spec.profile,
            capability=req_cap,
            diagnostics=[
                Diagnostic(
                    code="target_root_unsafe",
                    message=str(err),
                )
            ],
        )

    if not resolved_cwd.is_dir():
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            profile=target_spec.profile,
            capability=req_cap,
            cwd=str(resolved_cwd),
            diagnostics=[
                Diagnostic(
                    code="target_root_missing",
                    message=f"Target root directory does not exist: {resolved_cwd}",
                )
            ],
        )

    # 4. Capability and Selector Validation
    valid_capabilities = {"format.check", "lint", "typecheck", "test.targeted", "test.full", "build"}
    if req_cap not in valid_capabilities:
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            profile=target_spec.profile,
            capability=req_cap,
            cwd=str(resolved_cwd),
            diagnostics=[
                Diagnostic(
                    code="capability_unknown",
                    message=f"Unknown capability '{req_cap}'. Supported: {sorted(valid_capabilities)}",
                )
            ],
        )

    if req_cap == "test.targeted":
        if not selector or not selector.strip():
            return CapabilityResolution(
                ok=False,
                target=selected_target_name,
                profile=target_spec.profile,
                capability=req_cap,
                cwd=str(resolved_cwd),
                diagnostics=[
                    Diagnostic(
                        code="selector_required",
                        message="Capability 'test.targeted' requires a non-empty selector",
                    )
                ],
            )
    else:
        if selector is not None and selector.strip() != "":
            return CapabilityResolution(
                ok=False,
                target=selected_target_name,
                profile=target_spec.profile,
                capability=req_cap,
                cwd=str(resolved_cwd),
                diagnostics=[
                    Diagnostic(
                        code="selector_forbidden",
                        message=f"Capability '{req_cap}' does not accept a selector",
                    )
                ],
            )

    # 5. Registry Lookup
    registry = get_bundled_registry()
    if target_spec.profile not in registry.profiles:
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            profile=target_spec.profile,
            capability=req_cap,
            cwd=str(resolved_cwd),
            diagnostics=[
                Diagnostic(
                    code="profile_unknown",
                    message=f"Profile '{target_spec.profile}' not found in registry",
                )
            ],
        )

    profile_def = registry.profiles[target_spec.profile]
    cap_enum = CapabilityName(req_cap)
    if cap_enum not in profile_def.capabilities:
        return CapabilityResolution(
            ok=False,
            target=selected_target_name,
            profile=target_spec.profile,
            capability=cap_enum,
            cwd=str(resolved_cwd),
            diagnostics=[
                Diagnostic(
                    code="capability_unknown",
                    message=f"Capability '{req_cap}' not supported for profile '{target_spec.profile}'",
                )
            ],
        )

    cap_def = profile_def.capabilities[cap_enum]

    # 6. Build argv & requirements per profile
    argv: List[str] = []
    requirements: List[str] = list(cap_def.requirements)

    if target_spec.profile == "python":
        if cap_enum == CapabilityName.TEST_TARGETED:
            # Selector is one atom
            argv = [atom.format(selector=selector) if "{selector}" in atom else atom for atom in (cap_def.argv_template or [])]
        else:
            argv = list(cap_def.argv or [])

    elif target_spec.profile == "rust":
        if cap_enum == CapabilityName.TEST_TARGETED:
            argv = [atom.format(selector=selector) if "{selector}" in atom else atom for atom in (cap_def.argv_template or [])]
        else:
            argv = list(cap_def.argv or [])

    elif target_spec.profile == "javascript":
        assert isinstance(target_spec, JsTargetSpec)
        pkg_manager, js_diag = _detect_js_package_manager(resolved_cwd, target_spec)
        if js_diag or not pkg_manager:
            return CapabilityResolution(
                ok=False,
                target=selected_target_name,
                profile=target_spec.profile,
                capability=cap_enum,
                cwd=str(resolved_cwd),
                diagnostics=[js_diag] if js_diag else [],
            )

        requirements = [pkg_manager]

        # Determine script label
        script_key = cap_def.script_key or req_cap
        script_label = None
        if target_spec.scripts:
            if script_key in target_spec.scripts:
                script_label = target_spec.scripts[script_key]
            elif req_cap in target_spec.scripts:
                script_label = target_spec.scripts[req_cap]

        if not script_label:
            # Fall back to default script from profile
            default_scripts = profile_def.default_scripts or {}
            script_label = default_scripts.get(script_key, default_scripts.get(req_cap, req_cap))

        argv = [pkg_manager, "run", script_label]
        if cap_def.append_selector and selector:
            argv.extend(["--", selector])

    return CapabilityResolution(
        ok=True,
        target=selected_target_name,
        profile=target_spec.profile,
        capability=cap_enum,
        cwd=str(resolved_cwd),
        argv=argv,
        timeout_seconds=cap_def.timeout_seconds,
        requirements=requirements,
        diagnostics=[],
    )
