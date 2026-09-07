"""Stack profiles package."""

from loop.stack_profiles.doctor import doctor_project_profiles
from loop.stack_profiles.execution import (
    CapabilityCheckSpec,
    CapabilityExecutionEvidence,
    CapabilityExecutionResult,
    ExecutionStatus,
    compute_declaration_fingerprint,
    execute_capability,
)
from loop.stack_profiles.resolver import load_project_manifest, resolve_capability
from loop.stack_profiles.schemas import (
    CapabilityName,
    CapabilityRequest,
    CapabilityResolution,
    Diagnostic,
    DiagnosticCode,
    DoctorCheckResult,
    DoctorReport,
    JsTargetSpec,
    ProjectManifest,
    PythonTargetSpec,
    RustTargetSpec,
    TargetSpec,
    validate_workspace_containment,
)

__all__ = [
    "CapabilityCheckSpec",
    "CapabilityExecutionEvidence",
    "CapabilityExecutionResult",
    "CapabilityName",
    "CapabilityRequest",
    "CapabilityResolution",
    "Diagnostic",
    "DiagnosticCode",
    "DoctorCheckResult",
    "DoctorReport",
    "ExecutionStatus",
    "JsTargetSpec",
    "ProjectManifest",
    "PythonTargetSpec",
    "RustTargetSpec",
    "TargetSpec",
    "compute_declaration_fingerprint",
    "doctor_project_profiles",
    "execute_capability",
    "load_project_manifest",
    "resolve_capability",
    "validate_workspace_containment",
]
