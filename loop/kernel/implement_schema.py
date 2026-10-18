from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SCHEMA_IMPLEMENT = "epic-implement/v1"

ImplementStepStatus = Literal["in_progress", "completed"]
CheckpointStatus = Literal["pending", "done"]

STEP_STATUS_ALIASES: dict[str, ImplementStepStatus] = {
    "in-progress": "in_progress",
    "inprogress": "in_progress",
    "progress": "in_progress",
    "wip": "in_progress",
    "active": "in_progress",
    "complete": "completed",
    "done": "completed",
    "finished": "completed",
    "passed": "completed",
}

CHECKPOINT_STATUS_ALIASES: dict[str, CheckpointStatus] = {
    "pass": "done",
    "passed": "done",
    "complete": "done",
    "completed": "done",
    "ok": "done",
    "success": "done",
    "fixed": "done",
    "green": "done",
    "todo": "pending",
    "open": "pending",
    "wip": "pending",
    "in_progress": "pending",
    "in-progress": "pending",
}


def _norm_token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def coerce_step_status(value: Any) -> ImplementStepStatus:
    raw = _norm_token(value)
    if raw in {"in_progress", "completed"}:
        return raw  # type: ignore[return-value]
    if raw in STEP_STATUS_ALIASES:
        return STEP_STATUS_ALIASES[raw]
    raise ValueError(
        f"implement status must be one of ['in_progress', 'completed'] "
        f"(aliases: {sorted(STEP_STATUS_ALIASES)}); got {value!r}"
    )


def coerce_checkpoint_status(value: Any) -> CheckpointStatus:
    raw = _norm_token(value)
    if raw in {"pending", "done"}:
        return raw  # type: ignore[return-value]
    if raw in CHECKPOINT_STATUS_ALIASES:
        return CHECKPOINT_STATUS_ALIASES[raw]
    raise ValueError(
        f"checkpoint status must be one of ['pending', 'done'] "
        f"(aliases: {sorted(CHECKPOINT_STATUS_ALIASES)}); got {value!r}"
    )


class ImplementCheckpoint(BaseModel):
    id: str
    criterion: str = ""
    status: CheckpointStatus
    verify: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> CheckpointStatus:
        return coerce_checkpoint_status(value)


class ImplementArtifact(BaseModel):
    schema_id: str = Field(
        validation_alias="schema",
        serialization_alias="schema",
    )
    role: str
    step_id: str
    plan_id: str
    status: ImplementStepStatus
    done: list[Any] = Field(default_factory=list)
    files: list[Any] = Field(default_factory=list)
    deletes: list[Any] = Field(default_factory=list)
    tests: list[Any] = Field(default_factory=list)
    integration_check: list[Any] = Field(default_factory=list)
    checkpoints: list[ImplementCheckpoint] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("schema_id")
    @classmethod
    def _schema(cls, value: str) -> str:
        if value != SCHEMA_IMPLEMENT:
            raise ValueError(f"unsupported implement schema: {value!r}")
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: Any) -> ImplementStepStatus:
        return coerce_step_status(value)

    @field_validator("done", "files", "deletes", "tests", "integration_check", mode="before")
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
    """Surgical rewrite of status aliases; preserves comments/order."""
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
        if in_checkpoints and checkpoints_indent is not None and indent <= checkpoints_indent and key != "-":
            in_checkpoints = False
            checkpoints_indent = None
        if key == "status" and ":" in stripped:
            raw_value = stripped.split(":", 1)[1].strip()
            # drop inline comment for parse; keep original suffix rewrite via full match
            value_token = raw_value.split("#", 1)[0].strip().strip("\"'")
            try:
                if in_checkpoints:
                    coerced = coerce_checkpoint_status(value_token)
                else:
                    coerced = coerce_step_status(value_token)
            except ValueError:
                out.append(line)
                continue
            if _norm_token(value_token) != coerced:
                comment = ""
                if "#" in raw_value:
                    comment = " #" + raw_value.split("#", 1)[1]
                # preserve list-item dash indent style
                prefix = line[: len(line) - len(stripped)]
                out.append(f"{prefix}status: {coerced}{comment}\n" if line.endswith("\n") else f"{prefix}status: {coerced}{comment}")
                continue
        out.append(line)
    return "".join(out)


def validate_implement_artifact(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
    rewrite: bool = True,
) -> ImplementArtifact:
    """Load, coerce aliases, pydantic-validate, optionally rewrite file."""
    if not path.is_file():
        raise ValueError(f"implement artifact missing: {path}")
    original = path.read_text(encoding="utf-8")
    try:
        payload = yaml.safe_load(original) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid implement YAML: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"implement YAML root must be a mapping: {path}")

    payload, repairs = _coerce_payload_aliases(payload)
    try:
        model = ImplementArtifact.model_validate(payload)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg')}"
            for err in exc.errors()
        )
        raise ValueError(f"invalid implement artifact {path}: {errors}") from exc

    if expected_step_id and model.step_id != expected_step_id:
        raise ValueError(
            f"implement step_id mismatch: expected {expected_step_id!r}, got {model.step_id!r} ({path})"
        )
    if expected_plan_id and model.plan_id != expected_plan_id:
        raise ValueError(
            f"implement plan_id mismatch: expected {expected_plan_id!r}, got {model.plan_id!r} ({path})"
        )

    if rewrite and repairs:
        rewritten = _rewrite_status_aliases(original)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
    return model


def implement_artifact_problems(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> list[str]:
    try:
        validate_implement_artifact(
            path,
            expected_step_id=expected_step_id,
            expected_plan_id=expected_plan_id,
            rewrite=True,
        )
    except ValueError as exc:
        return [str(exc)]
    return []


def _force_status_literals(
    text: str,
    *,
    step_status: ImplementStepStatus,
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


def _evidence_ready(model: ImplementArtifact) -> bool:
    return bool(model.done or model.files or model.tests or model.integration_check)


def flush_implement_for_verify(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> ImplementArtifact:
    """Atomic pre-verify status write (machine-owned).

    Sets step ``in_progress`` and every checkpoint ``done``.
    FORBIDDEN for agents to invent status literals — call this instead.
    """
    model = validate_implement_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=True,
    )
    if not model.checkpoints:
        raise ValueError(f"implement artifact has no checkpoints to flush: {path}")
    if not _evidence_ready(model):
        raise ValueError(
            f"cannot flush implement statuses: evidence empty "
            f"(need non-empty done|files|tests|integration_check): {path}"
        )
    original = path.read_text(encoding="utf-8")
    rewritten = _force_status_literals(
        original, step_status="in_progress", checkpoint_status="done"
    )
    if rewritten != original:
        path.write_text(rewritten, encoding="utf-8")
    return validate_implement_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=False,
    )


def complete_implement_artifact(
    path: Path,
    *,
    expected_step_id: str | None = None,
    expected_plan_id: str | None = None,
) -> ImplementArtifact:
    """Atomic finish status write: step ``completed`` + all checkpoints ``done``."""
    model = flush_implement_for_verify(
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
    return validate_implement_artifact(
        path,
        expected_step_id=expected_step_id,
        expected_plan_id=expected_plan_id,
        rewrite=False,
    )


__all__ = [
    "CHECKPOINT_STATUS_ALIASES",
    "CheckpointStatus",
    "ImplementArtifact",
    "ImplementCheckpoint",
    "ImplementStepStatus",
    "SCHEMA_IMPLEMENT",
    "STEP_STATUS_ALIASES",
    "coerce_checkpoint_status",
    "coerce_step_status",
    "complete_implement_artifact",
    "flush_implement_for_verify",
    "implement_artifact_problems",
    "validate_implement_artifact",
]
