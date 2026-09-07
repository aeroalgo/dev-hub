"""Stack profile capability execution models, declaration contracts, executor, and fingerprints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from loop.stack_profiles.resolver import resolve_capability
from loop.stack_profiles.schemas import (
    CapabilityName,
    Diagnostic,
    DiagnosticCode,
    NonEmptyStr,
)

ExecutionStatus = Literal[
    "succeeded",
    "resolution_failed",
    "spawn_failed",
    "timed_out",
    "failed",
]


class CapabilityCheckSpec(BaseModel):
    """Strict decompose capability_checks declaration item."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    target: NonEmptyStr
    capability: CapabilityName
    selector: Optional[str] = None

    @model_validator(mode="after")
    def validate_selector_rules(self) -> CapabilityCheckSpec:
        cap_val = self.capability if isinstance(self.capability, str) else self.capability.value
        if cap_val == CapabilityName.TEST_TARGETED.value:
            if not self.selector or not self.selector.strip():
                raise ValueError("selector is required for capability test.targeted")
        else:
            if self.selector is not None and self.selector != "":
                raise ValueError(
                    f"selector is forbidden for capability '{cap_val}'"
                )
        return self


def compute_declaration_fingerprint(
    role: str,
    epic_id: str,
    step_id: str,
    declaration: CapabilityCheckSpec,
) -> str:
    """Compute deterministic canonical sha256 fingerprint for a capability check declaration."""
    cap_val = declaration.capability if isinstance(declaration.capability, str) else declaration.capability.value
    payload = {
        "role": str(role).strip(),
        "epic_id": str(epic_id).strip(),
        "step_id": str(step_id).strip(),
        "target": str(declaration.target).strip(),
        "capability": str(cap_val).strip(),
        "selector": declaration.selector.strip() if declaration.selector else None,
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class CapabilityExecutionResult(BaseModel):
    """Typed outcome of capability execution."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: Literal["stack-capability-execution/v1"] = Field(
        default="stack-capability-execution/v1", alias="schema"
    )
    ok: bool
    request_fingerprint: Optional[str] = None
    target: Optional[str] = None
    profile: Optional[str] = None
    capability: Optional[str] = None
    cwd: Optional[str] = None
    argv: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[int] = None
    status: ExecutionStatus
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    output_truncated: bool = False
    diagnostics: List[Diagnostic] = Field(default_factory=list)


class CapabilityExecutionEvidence(BaseModel):
    """Persisted evidence model bound to declaration fingerprint and step."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    schema_version: Literal["stack-capability-evidence/v1"] = Field(
        default="stack-capability-evidence/v1", alias="schema"
    )
    declaration_fingerprint: NonEmptyStr
    role: NonEmptyStr
    epic_id: NonEmptyStr
    step_id: NonEmptyStr
    target: NonEmptyStr
    capability: NonEmptyStr
    status: ExecutionStatus
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None
    recorded_at: NonEmptyStr
    diagnostics: List[Diagnostic] = Field(default_factory=list)


def execute_capability(
    project_root: Path,
    declaration: CapabilityCheckSpec,
) -> CapabilityExecutionResult:
    """Public executor: resolve capability and run strictly with resolver argv/cwd/timeout."""
    cap_val = declaration.capability if isinstance(declaration.capability, str) else declaration.capability.value
    target = str(declaration.target).strip()
    selector = declaration.selector.strip() if declaration.selector else None

    # Step 1: Resolve capability via resolver SoT
    resolution = resolve_capability(
        project_root,
        cap_val,
        target=target,
        selector=selector,
    )

    if not resolution.ok:
        return CapabilityExecutionResult(
            ok=False,
            target=target,
            profile=resolution.profile,
            capability=cap_val,
            cwd=resolution.cwd,
            argv=[],
            timeout_seconds=resolution.timeout_seconds,
            status="resolution_failed",
            exit_code=None,
            duration_ms=0,
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
            diagnostics=resolution.diagnostics,
        )

    # Step 2: Spawn subprocess with exact resolver argv, cwd, timeout and shell=False
    start_time = time.monotonic()
    timeout = resolution.timeout_seconds
    cwd = resolution.cwd
    argv = list(resolution.argv)

    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as err:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return CapabilityExecutionResult(
            ok=False,
            target=target,
            profile=resolution.profile,
            capability=cap_val,
            cwd=cwd,
            argv=argv,
            timeout_seconds=timeout,
            status="spawn_failed",
            exit_code=None,
            duration_ms=duration_ms,
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
            diagnostics=[
                Diagnostic(
                    code="spawn_failed",
                    message=f"Failed to spawn process '{argv[0]}': {err}",
                )
            ],
        )

    # Step 3: Communicate with deadline enforcement
    try:
        raw_stdout, raw_stderr = proc.communicate(timeout=timeout)
        duration_ms = int((time.monotonic() - start_time) * 1000)
        exit_code = proc.returncode
        stdout_bytes = len(raw_stdout) if raw_stdout else 0
        stderr_bytes = len(raw_stderr) if raw_stderr else 0

        if exit_code == 0:
            return CapabilityExecutionResult(
                ok=True,
                target=target,
                profile=resolution.profile,
                capability=cap_val,
                cwd=cwd,
                argv=argv,
                timeout_seconds=timeout,
                status="succeeded",
                exit_code=0,
                duration_ms=duration_ms,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                output_truncated=False,
                diagnostics=[],
            )
        else:
            return CapabilityExecutionResult(
                ok=False,
                target=target,
                profile=resolution.profile,
                capability=cap_val,
                cwd=cwd,
                argv=argv,
                timeout_seconds=timeout,
                status="failed",
                exit_code=exit_code,
                duration_ms=duration_ms,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                output_truncated=False,
                diagnostics=[
                    Diagnostic(
                        code="command_failed",
                        message=f"Command exited with non-zero status code: {exit_code}",
                    )
                ],
            )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass

        return CapabilityExecutionResult(
            ok=False,
            target=target,
            profile=resolution.profile,
            capability=cap_val,
            cwd=cwd,
            argv=argv,
            timeout_seconds=timeout,
            status="timed_out",
            exit_code=proc.returncode if proc.returncode is not None else -9,
            duration_ms=duration_ms,
            stdout_bytes=0,
            stderr_bytes=0,
            output_truncated=False,
            diagnostics=[
                Diagnostic(
                    code="process_timed_out",
                    message=f"Process timed out: exceeded deadline of {timeout} seconds and was terminated",
                )
            ],
        )
