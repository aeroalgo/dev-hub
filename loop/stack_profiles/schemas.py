"""Stack profiles schemas and models for dev-hub."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# TM-001/002/003/004/005/006/007/008/010/011
DiagnosticCode = Literal[
    "project_manifest_missing",
    "project_manifest_invalid",
    "target_root_unsafe",
    "target_root_missing",
    "target_root_duplicate",
    "target_selection_required",
    "target_unknown",
    "profile_unknown",
    "capability_unknown",
    "selector_required",
    "selector_forbidden",
    "js_package_manager_missing",
    "js_package_manager_ambiguous",
    "js_package_manager_invalid",
    "js_script_invalid",
    "tool_missing",
    "tool_probe_failed",
    "legacy_config_detected",
    "capability_target_required",
    "capability_declaration_invalid",
    "spawn_failed",
    "process_timed_out",
    "command_failed",
]

DoctorCheckStatus = Literal["pass", "fail", "warn"]


class DoctorCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    target: Optional[str] = None
    status: DoctorCheckStatus
    message: str
    detail: Optional[str] = None


class DoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["doctor-report/v1"] = Field(default="doctor-report/v1", alias="schema")
    ok: bool
    checks: List[DoctorCheckResult] = Field(default_factory=list)
    diagnostics: List[Diagnostic] = Field(default_factory=list)


class CapabilityName(StrEnum):
    """Exactly six verify-first capability vocabulary items (FR-007)."""

    FORMAT_CHECK = "format.check"
    LINT = "lint"
    TYPECHECK = "typecheck"
    TEST_TARGETED = "test.targeted"
    TEST_FULL = "test.full"
    BUILD = "build"


class ProfileName(StrEnum):
    """Exactly three supported stack profiles."""

    PYTHON = "python"
    RUST = "rust"
    JAVASCRIPT = "javascript"


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: DiagnosticCode
    message: str
    target: Optional[str] = None
    path: Optional[str] = None


class BaseTargetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: NonEmptyStr


class PythonTargetSpec(BaseTargetSpec):
    profile: Literal["python"]


class RustTargetSpec(BaseTargetSpec):
    profile: Literal["rust"]


JsPackageManager = Literal["npm", "pnpm", "yarn", "bun"]


class JsTargetSpec(BaseTargetSpec):
    profile: Literal["javascript"]
    package_manager: Optional[JsPackageManager] = None
    scripts: Optional[Dict[NonEmptyStr, NonEmptyStr]] = None


TargetSpec = Annotated[
    Union[PythonTargetSpec, RustTargetSpec, JsTargetSpec],
    Field(discriminator="profile"),
]


class ProjectManifest(BaseModel):
    """dev-hub-project/v1 manifest representation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["dev-hub-project/v1"] = Field(alias="schema")
    workflow_pack: Optional[NonEmptyStr] = None
    default_target: Optional[NonEmptyStr] = None
    targets: Dict[NonEmptyStr, TargetSpec]

    @field_validator("targets")
    @classmethod
    def validate_targets_non_empty(
        cls, v: Dict[NonEmptyStr, TargetSpec]
    ) -> Dict[NonEmptyStr, TargetSpec]:
        if not v:
            raise ValueError("targets map must not be empty")
        return v

    @model_validator(mode="after")
    def validate_default_target_and_roots(self) -> ProjectManifest:
        if self.default_target is not None and self.default_target not in self.targets:
            raise ValueError(
                f"default_target '{self.default_target}' is not defined in targets"
            )

        # Check duplicate normalized root paths across targets
        seen_roots: Dict[str, str] = {}
        for target_name, target_spec in self.targets.items():
            norm_root = str(Path(target_spec.root).as_posix())
            if norm_root in seen_roots:
                raise ValueError(
                    f"Duplicate target root '{target_spec.root}' in targets '{seen_roots[norm_root]}' and '{target_name}'"
                )
            seen_roots[norm_root] = target_name

        return self


class CapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: CapabilityName
    target: Optional[NonEmptyStr] = None
    selector: Optional[str] = None

    @model_validator(mode="after")
    def validate_selector_rules(self) -> CapabilityRequest:
        if self.capability == CapabilityName.TEST_TARGETED:
            if not self.selector or not self.selector.strip():
                raise ValueError("selector is required for capability test.targeted")
        else:
            if self.selector is not None and self.selector != "":
                raise ValueError(
                    f"selector is forbidden for capability '{self.capability}'"
                )
        return self


class CapabilityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: Literal["stack-capability-resolution/v1"] = Field(
        default="stack-capability-resolution/v1", alias="schema"
    )
    ok: bool
    target: Optional[str] = None
    profile: Optional[str] = None
    capability: Optional[str] = None
    cwd: Optional[str] = None
    argv: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[int] = None
    requirements: List[str] = Field(default_factory=list)
    diagnostics: List[Diagnostic] = Field(default_factory=list)


def validate_workspace_containment(project_root: Path, target_root: str) -> Path:
    """Ensure target root resolves within project root without path traversal."""
    resolved_project = project_root.resolve()
    target_path = Path(target_root)
    if target_path.is_absolute():
        raise ValueError(f"target root must be workspace-relative: '{target_root}'")

    resolved_target = (resolved_project / target_path).resolve()

    try:
        resolved_target.relative_to(resolved_project)
    except ValueError as err:
        raise ValueError(
            f"target root '{target_root}' escapes workspace root '{resolved_project}'"
        ) from err

    return resolved_target
