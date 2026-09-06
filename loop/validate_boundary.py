"""loop.validate_boundary — unified boundary schema validator (FR-003b)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from loop.schemas.boundary_registry import BOUNDARY_REGISTRY
from loop.schemas.validate_result import ValidateResult, SCHEMA_LOOP_VALIDATE_RESULT


def validate_boundary(schema_id: str, raw_json: str | dict[str, Any]) -> ValidateResult:
    """Validate candidate payload against schema_id from BOUNDARY_REGISTRY.

    Accepts JSON string or pre-parsed dict.
    Returns ValidateResult (valid=True/False, errors, diagnostic_codes).
    """
    if schema_id not in BOUNDARY_REGISTRY:
        return ValidateResult(
            schema=SCHEMA_LOOP_VALIDATE_RESULT,
            schema_id=schema_id,
            valid=False,
            errors=[f"Unknown schema_id: {schema_id!r}"],
            diagnostic_codes=["schema_unknown_schema_id"],
        )

    model_cls = BOUNDARY_REGISTRY[schema_id]

    payload: Any = raw_json
    if isinstance(raw_json, str):
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            return ValidateResult(
                schema=SCHEMA_LOOP_VALIDATE_RESULT,
                schema_id=schema_id,
                valid=False,
                errors=[f"JSONDecodeError: {exc}"],
                diagnostic_codes=["schema_json_decode_error"],
            )

    if not isinstance(payload, dict):
        return ValidateResult(
            schema=SCHEMA_LOOP_VALIDATE_RESULT,
            schema_id=schema_id,
            valid=False,
            errors=["Payload must be a JSON object (dict)"],
            diagnostic_codes=["schema_payload_not_dict"],
        )

    # Wire requirement: schema field must be explicitly present on the wire payload
    if "schema" not in payload and "schema_version" not in payload:
        return ValidateResult(
            schema=SCHEMA_LOOP_VALIDATE_RESULT,
            schema_id=schema_id,
            valid=False,
            errors=["Missing required 'schema' field on wire payload"],
            diagnostic_codes=["schema_missing_schema"],
        )

    try:
        model_cls.model_validate(payload)
        return ValidateResult(
            schema=SCHEMA_LOOP_VALIDATE_RESULT,
            schema_id=schema_id,
            valid=True,
            errors=[],
            diagnostic_codes=[],
        )
    except ValidationError as exc:
        errors = [str(err) for err in exc.errors()]
        diagnostic_codes: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            err_type = err.get("type", "invalid")
            if loc:
                diagnostic_codes.append(f"schema_{err_type}_{loc}")
            else:
                diagnostic_codes.append(f"schema_{err_type}")
        return ValidateResult(
            schema=SCHEMA_LOOP_VALIDATE_RESULT,
            schema_id=schema_id,
            valid=False,
            errors=errors,
            diagnostic_codes=diagnostic_codes or ["schema_validation_error"],
        )
