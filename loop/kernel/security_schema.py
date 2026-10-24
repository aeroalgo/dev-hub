from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .implement_schema import (
    CHECKPOINT_STATUS_ALIASES,
    STEP_STATUS_ALIASES,
    CheckpointStatus,
    coerce_checkpoint_status,
    coerce_step_status,
)

SCHEMA_SECURITY = "epic-security/v1"

SecurityStepStatus = Literal["in_progress", "completed"]


class SecurityCheckpoint(BaseModel):
    id: str
    criterion: str = ""
    status: CheckpointStatus
    verify: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> CheckpointStatus:
        return coerce_checkpoint_status(value)


class SecurityArtifact(BaseModel):
    schema_id: str = Field(
        validation_alias="schema",
        serialization_alias="schema",
    )
    role: str
    step_id: str
    plan_id: str
    status: SecurityStepStatus
    title: str = ""
    date: str | None = None
    audit_surface: str | None = None
    scope_paths: list[Any] = Field(default_factory=list)
    threats: list[Any] = Field(default_factory=list)
    evidence_commands: list[Any] = Field(default_factory=list)
    findings: list[Any] = Field(default_factory=list)
    decompose_ref: str | None = None
    checkpoints: list[SecurityCheckpoint] = Field(default_factory=list)
    resume_from: str | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("date", mode="before")
    @classmethod
    def _date(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @field_validator("schema_id")
    @classmethod
    def _schema(cls, value: str) -> str:
        if value != SCHEMA_SECURITY:
            raise ValueError(f"unsupported security schema: {value!r}")
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> SecurityStepStatus:
        return coerce_step_status(value)

    @field_validator(
        "scope_paths",
        "threats",
        "evidence_commands",
        "findings",
        mode="before",
    )
    @classmethod
    def _lists(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        raise ValueError("must be a list")

    @field_validator("checkpoints", mode="before")
    @classmethod
    def _checkpoints(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        raise ValueError("checkpoints must be a list")


def _coerce_payload_aliases(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize known aliases in-place; return (payload, human repairs)."""
    repairs: list[str] = []
    if "status" in payload:
        before = payload.get("status")
        try:
            after = coerce_step_status(before)
        except ValueError:
            after = before
        if after != before:
            payload["status"] = after
            repairs.append(f"status: {before!r} → {after!r}")
    checkpoints = payload.get("checkpoints")
    if isinstance(checkpoints, list):
        for index, item in enumerate(checkpoints):
            if not isinstance(item, dict) or "status" not in item:
                continue
            before = item.get("status")
            try:
                after = coerce_checkpoint_status(before)
            except ValueError:
                continue
            if after != before:
                item["status"] = after
                repairs.append(f"checkpoints[{index}].status: {before!r} → {after!r}")
    return payload, repairs


def _rewrite_status_aliases(text: str) -> str:
    """Line-by-line alias rewriting preserving indentation, comments and blank lines."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_checkpoints = False
    checkpoints_indent: int | None = None
    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("#") or not stripped.strip():
            out.append(line)
            continue
        key = stripped.split(":", 1)[0].strip()
        if key == "checkpoints" and ":" in stripped:
            in_checkpoints = True
            checkpoints_indent = indent
            out.append(line)
            continue
        if in_checkpoints and checkpoints_indent is not None and indent <= checkpoints_indent and not stripped.startswith("-"):
            in_checkpoints = False
            checkpoints_indent = None
        if key == "status" and ":" in stripped:
            raw_value = stripped.split(":", 1)[1].strip()
            comment = ""
            if "#" in raw_value:
                raw_value, comment = raw_value.split("#", 1)
                raw_value = raw_value.strip()
                comment = " #" + comment
            raw_token = raw_value.strip("'\"")
            try:
                canonical = (
                    coerce_checkpoint_status(raw_token)
                    if in_checkpoints
                    else coerce_step_status(raw_token)
                )
            except ValueError:
                canonical = raw_token
            prefix = line[: len(line) - len(stripped)]
            ending = "\n" if line.endswith("\n") else ""
            out.append(f"{prefix}status: {canonical}{comment}{ending}")
            continue
        out.append(line)
    return "".join(out)


def validate_security_artifact(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
    rewrite: bool = False,
) -> SecurityArtifact:
    """Validate a security execute artifact against schema epic-security/v1.

    When ``rewrite=True``, known alias spellings (e.g. ``passed`` → ``done``)
    are rewritten in-place.
    """
    if not path.is_file():
        raise FileNotFoundError(f"security artifact not found: {path}")

    original = path.read_text(encoding="utf-8")
    try:
        raw_payload = yaml.safe_load(original)
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed YAML in security artifact {path}: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise ValueError(f"security artifact must be a YAML mapping: {path}")

    coerced_payload, repairs = _coerce_payload_aliases(dict(raw_payload))

    try:
        model = SecurityArtifact.model_validate(coerced_payload)
    except ValidationError as exc:
        messages = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        raise ValueError(
            f"security artifact validation failed ({path}): {'; '.join(messages)}"
        ) from exc

    if expected_step_id and model.step_id != expected_step_id:
        raise ValueError(
            f"security step_id mismatch: expected {expected_step_id!r}, got {model.step_id!r} ({path})"
        )
    if expected_plan_id and model.plan_id != expected_plan_id:
        raise ValueError(
            f"security plan_id mismatch: expected {expected_plan_id!r}, got {model.plan_id!r} ({path})"
        )

    if rewrite and repairs:
        rewritten = _rewrite_status_aliases(original)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
    return model


def security_artifact_problems(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> list[str]:
    try:
        validate_security_artifact(
            path,
            expected_step_id=expected_step_id,
            expected_plan_id=expected_plan_id,
            rewrite=True,
        )
    except (ValueError, FileNotFoundError) as exc:
        return [str(exc)]
    return []


def _force_status_literals(
    text: str,
    *,
    step_status: SecurityStepStatus,
    checkpoint_status: CheckpointStatus,
) -> str:
    """Machine-only writer: overwrite every status field to the given Literals."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_checkpoints = False
    checkpoints_indent: int | None = None
    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("#") or not stripped.strip():
            out.append(line)
            continue
        key = stripped.split(":", 1)[0].strip()
        if key == "checkpoints" and ":" in stripped:
            in_checkpoints = True
            checkpoints_indent = indent
            out.append(line)
            continue
        if in_checkpoints and checkpoints_indent is not None and indent <= checkpoints_indent and not stripped.startswith("-"):
            in_checkpoints = False
            checkpoints_indent = None
        if key == "status" and ":" in stripped:
            raw_value = stripped.split(":", 1)[1].strip()
            comment = ""
            if "#" in raw_value:
                comment = " #" + raw_value.split("#", 1)[1]
            target = checkpoint_status if in_checkpoints else step_status
            prefix = line[: len(line) - len(stripped)]
            ending = "\n" if line.endswith("\n") else ""
            out.append(f"{prefix}status: {target}{comment}{ending}")
            continue
        out.append(line)
    return "".join(out)


def _evidence_ready(model: SecurityArtifact) -> bool:
    return bool(
        model.evidence_commands
        or model.scope_paths
        or model.threats
        or model.findings
    )


def flush_security_for_verify(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> SecurityArtifact:
    """Atomic pre-verify status write (machine-owned).

    Sets step ``in_progress`` and every checkpoint ``done``.
    """
    model = validate_security_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=True,
    )
    if not model.checkpoints:
        raise ValueError(f"security artifact has no checkpoints to flush: {path}")
    if not _evidence_ready(model):
        raise ValueError(
            f"cannot flush security statuses: evidence empty "
            f"(need non-empty scope_paths|threats|evidence_commands|findings): {path}"
        )
    original = path.read_text(encoding="utf-8")
    rewritten = _force_status_literals(
        original, step_status="in_progress", checkpoint_status="done"
    )
    if rewritten != original:
        path.write_text(rewritten, encoding="utf-8")
    return validate_security_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=False,
    )


def complete_security_artifact(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> SecurityArtifact:
    """Atomic finish status write: step ``completed`` + all checkpoints ``done``."""
    model = flush_security_for_verify(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
    )
    original = path.read_text(encoding="utf-8")
    rewritten = _force_status_literals(
        original, step_status="completed", checkpoint_status="done"
    )
    if rewritten != original:
        path.write_text(rewritten, encoding="utf-8")
    return validate_security_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=False,
    )


__all__ = [
    "CHECKPOINT_STATUS_ALIASES",
    "CheckpointStatus",
    "SCHEMA_SECURITY",
    "STEP_STATUS_ALIASES",
    "SecurityArtifact",
    "SecurityCheckpoint",
    "SecurityStepStatus",
    "coerce_checkpoint_status",
    "coerce_step_status",
    "complete_security_artifact",
    "flush_security_for_verify",
    "security_artifact_problems",
    "validate_security_artifact",
]
