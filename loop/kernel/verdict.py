from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .inventory import (
    INVENTORY_AGENT_ALIASES,
    INVENTORY_SCHEMA_MODELS,
    MANAGED_INVENTORY_AGENTS,
    SCHEMA_SUNSET_INVENTORY,
    SunsetReport,
    inventory_schema_for_agent,
    normalize_inventory_agent_id,
)


SCHEMA_GATE_VERDICT = "loop-gate-verdict/v1"
SCHEMA_REPAIR_RESULT = "loop-repair-result/v1"
SCHEMA_VALIDATE_RESULT = "loop-validate-result/v1"
GateVerdictValue = Literal["PASS", "FAIL", "BLOCKED"]
RepairStatus = Literal["done", "partial", "fail"]

MANAGED_GATE_AGENTS = frozenset(
    {
        "verify-implement",
        "verify-bugfix",
        "verify-qa",
        "verify-decompose",
        "analyze-verify",
        "verify-script",
        "verify-edit",
        "verify-publish",
    }
)
MANAGED_REPAIR_AGENTS = frozenset({"gate-repair"})
MANAGED_SUBAGENTS = MANAGED_GATE_AGENTS | MANAGED_REPAIR_AGENTS | MANAGED_INVENTORY_AGENTS
AGENT_ALIASES = {
    "verify": "verify-implement",
    "reviewer": "verify-qa",
    "explore": "explorer",
    **INVENTORY_AGENT_ALIASES,
}
REPAIR_RESULT_ONLY_FIELDS = frozenset(
    {
        "parent_evidence_id",
        "recorded_at",
        "agent_id",
        "status",
        "fixed_blockers",
        "remaining_blockers",
        "schema",
    }
)
_JSON_FENCE_RE = re.compile(r"```\s*json[^\n`]*\n(.*?)\n\s*```", re.IGNORECASE | re.DOTALL)
_PROMPT_INCOMPLETE_RE = re.compile(r"^prompt_incomplete:(?P<section>.+)$", re.IGNORECASE)


def normalize_agent_id(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in AGENT_ALIASES:
        return AGENT_ALIASES[normalized]
    return normalize_inventory_agent_id(normalized)


class GateVerdict(BaseModel):
    schema_id: str = Field(
        default=SCHEMA_GATE_VERDICT,
        validation_alias="schema",
        serialization_alias="schema",
    )
    agent_id: str
    verdict: GateVerdictValue
    step_id: str
    session_id: str
    epic_id: str
    recorded_at: str
    evidence_sha256: str | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("schema_id")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        if value != SCHEMA_GATE_VERDICT:
            raise ValueError(f"unsupported schema: {value!r}")
        return value

    @field_validator("agent_id", "step_id", "session_id", "epic_id", mode="before")
    @classmethod
    def require_non_empty_string(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @field_validator("agent_id")
    @classmethod
    def normalize_agent(cls, value: str) -> str:
        normalized = normalize_agent_id(value)
        if normalized not in MANAGED_GATE_AGENTS:
            raise ValueError(f"unsupported gate agent: {value!r}")
        return normalized

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("recorded_at must be a non-empty ISO 8601 timestamp")
        cleaned = value.strip().replace("Z", "+00:00")
        try:
            datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError("recorded_at must be a valid ISO 8601 timestamp") from exc
        return value.strip()


class RepairResult(BaseModel):
    schema_id: str = Field(
        default=SCHEMA_REPAIR_RESULT,
        validation_alias="schema",
        serialization_alias="schema",
    )
    agent_id: str
    parent_evidence_id: str
    status: RepairStatus
    fixed_blockers: list[str]
    remaining_blockers: list[str]
    recorded_at: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("schema_id")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        if value != SCHEMA_REPAIR_RESULT:
            raise ValueError(f"unsupported schema: {value!r}")
        return value

    @field_validator("agent_id", "parent_evidence_id", "recorded_at", mode="before")
    @classmethod
    def require_non_empty_string(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string")
        return value.strip()

    @field_validator("fixed_blockers", "remaining_blockers", mode="before")
    @classmethod
    def require_string_list(cls, value: object) -> object:
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError("must be a list of non-empty strings")
        return [item.strip() for item in value]

    @field_validator("recorded_at")
    @classmethod
    def validate_repair_timestamp(cls, value: str) -> str:
        cleaned = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError("recorded_at must be a valid ISO 8601 timestamp") from exc
        return value


@dataclass(frozen=True)
class BoundaryIdentity:
    session_id: str
    epic_id: str
    step_id: str
    agent_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    schema_id: str
    errors: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()
    record: BaseModel | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VALIDATE_RESULT,
            "schema_id": self.schema_id,
            "valid": self.valid,
            "errors": list(self.errors),
            "diagnostic_codes": list(self.diagnostic_codes),
        }


def _result(
    valid: bool,
    schema_id: str,
    *,
    errors: list[str] | tuple[str, ...] = (),
    diagnostic_codes: list[str] | tuple[str, ...] = (),
    record: BaseModel | None = None,
) -> ValidationResult:
    return ValidationResult(
        valid=valid,
        schema_id=schema_id,
        errors=tuple(errors),
        diagnostic_codes=tuple(diagnostic_codes),
        record=record,
    )


def extract_json_fence(text: str | None) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    if not isinstance(text, str):
        return None, ("verdict_message_missing",)
    matches = list(_JSON_FENCE_RE.finditer(text))
    if not matches:
        return None, ("verdict_json_fence_missing",)
    if len(matches) != 1:
        return None, ("verdict_json_fence_multiple",)
    try:
        payload = json.loads(matches[0].group(1))
    except json.JSONDecodeError as exc:
        return None, ("verdict_json_decode_error", f"json_error:{exc.msg}")
    if not isinstance(payload, dict):
        return None, ("verdict_payload_not_object",)
    return payload, ()


def validate_boundary(
    schema_id: str,
    payload: str | dict[str, Any],
    *,
    identity: BoundaryIdentity | None = None,
) -> ValidationResult:
    schema_models: dict[str, type[BaseModel]] = {
        SCHEMA_GATE_VERDICT: GateVerdict,
        SCHEMA_REPAIR_RESULT: RepairResult,
        **INVENTORY_SCHEMA_MODELS,
    }
    model = schema_models.get(schema_id)
    if model is None:
        return _result(
            False,
            schema_id,
            errors=(f"unknown schema: {schema_id!r}",),
            diagnostic_codes=("schema_unknown",),
        )

    raw: Any = payload
    if isinstance(payload, str):
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            return _result(
                False,
                schema_id,
                errors=(str(exc),),
                diagnostic_codes=("verdict_json_decode_error",),
            )
    if not isinstance(raw, dict):
        return _result(
            False,
            schema_id,
            errors=("payload must be a JSON object",),
            diagnostic_codes=("verdict_payload_not_object",),
        )
    if "schema" not in raw:
        return _result(
            False,
            schema_id,
            errors=("payload must explicitly contain schema",),
            diagnostic_codes=("verdict_schema_missing",),
        )
    try:
        record = model.model_validate(raw)
    except ValidationError as exc:
        errors = tuple(str(error) for error in exc.errors())
        codes = tuple(
            "schema_" + str(error.get("type") or "invalid")
            for error in exc.errors()
        )
        return _result(False, schema_id, errors=errors, diagnostic_codes=codes)

    if identity is None or schema_id != SCHEMA_GATE_VERDICT:
        return _result(True, schema_id, record=record)

    mismatches: list[tuple[str, str]] = []
    for field in ("session_id", "epic_id", "step_id"):
        expected = str(getattr(identity, field))
        actual = str(getattr(record, field))
        if actual != expected:
            mismatches.append((field, actual))
    if identity.agent_id:
        expected_agent = normalize_agent_id(identity.agent_id)
        if record.agent_id != expected_agent:
            mismatches.append(("agent_id", record.agent_id))
    if mismatches:
        errors = tuple(
            f"{field} does not match boundary identity (received {value!r})"
            for field, value in mismatches
        )
        codes = tuple(f"verdict_wrong_{field}" for field, _ in mismatches)
        return _result(False, schema_id, errors=errors, diagnostic_codes=codes)
    return _result(True, schema_id, record=record)


def validate_message(
    message: str | None,
    *,
    identity: BoundaryIdentity | None = None,
) -> ValidationResult:
    payload, diagnostics = extract_json_fence(message)
    if payload is None:
        return _result(
            False,
            SCHEMA_GATE_VERDICT,
            errors=diagnostics,
            diagnostic_codes=diagnostics,
        )
    return validate_boundary(SCHEMA_GATE_VERDICT, payload, identity=identity)


def repair_contract_errors(
    record: RepairResult,
    *,
    session_id: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    errors: list[str] = []
    codes: list[str] = []
    if session_id and record.parent_evidence_id != session_id:
        errors.append(
            "parent_evidence_id must equal GATE_IDENTITY session_id "
            f"(expected {session_id!r}, received {record.parent_evidence_id!r})"
        )
        codes.append("repair_wrong_parent_evidence_id")
    for blocker in record.remaining_blockers:
        match = _PROMPT_INCOMPLETE_RE.match(blocker.strip())
        if match is None:
            continue
        section = match.group("section").strip().lower().replace(" ", "_")
        if section in REPAIR_RESULT_ONLY_FIELDS or section.replace("-", "_") in REPAIR_RESULT_ONLY_FIELDS:
            errors.append(
                "parent_evidence_id and other result-only fields are never missing prompt sections; "
                f"copy GATE_IDENTITY session_id into parent_evidence_id and repair BLOCKERS "
                f"(forbidden remaining_blocker {blocker!r})"
            )
            codes.append("repair_invented_prompt_incomplete")
    return tuple(errors), tuple(codes)


def validate_repair_message(
    message: str | None,
    *,
    session_id: str | None = None,
) -> ValidationResult:
    payload, diagnostics = extract_json_fence(message)
    if payload is None:
        return _result(
            False,
            SCHEMA_REPAIR_RESULT,
            errors=diagnostics,
            diagnostic_codes=diagnostics,
        )
    result = validate_boundary(SCHEMA_REPAIR_RESULT, payload)
    if not result.valid or result.record is None:
        return result
    if not isinstance(result.record, RepairResult):
        return result
    errors, codes = repair_contract_errors(result.record, session_id=session_id)
    if errors:
        return _result(
            False,
            SCHEMA_REPAIR_RESULT,
            errors=errors,
            diagnostic_codes=codes,
        )
    return result


def validate_inventory_message(
    message: str | None,
    *,
    agent_id: str,
) -> ValidationResult:
    schema_id = inventory_schema_for_agent(agent_id)
    if schema_id is None:
        return _result(
            False,
            SCHEMA_VALIDATE_RESULT,
            errors=(f"unsupported inventory agent: {agent_id!r}",),
            diagnostic_codes=("inventory_agent_unknown",),
        )
    payload, diagnostics = extract_json_fence(message)
    if payload is None:
        return _result(
            False,
            schema_id,
            errors=diagnostics,
            diagnostic_codes=diagnostics,
        )
    return validate_boundary(schema_id, payload)


__all__ = [
    "AGENT_ALIASES",
    "BoundaryIdentity",
    "GateVerdict",
    "MANAGED_GATE_AGENTS",
    "MANAGED_INVENTORY_AGENTS",
    "MANAGED_REPAIR_AGENTS",
    "MANAGED_SUBAGENTS",
    "REPAIR_RESULT_ONLY_FIELDS",
    "SCHEMA_GATE_VERDICT",
    "SCHEMA_REPAIR_RESULT",
    "SCHEMA_SUNSET_INVENTORY",
    "SCHEMA_VALIDATE_RESULT",
    "RepairResult",
    "SunsetReport",
    "ValidationResult",
    "extract_json_fence",
    "normalize_agent_id",
    "repair_contract_errors",
    "validate_boundary",
    "validate_inventory_message",
    "validate_message",
    "validate_repair_message",
]
