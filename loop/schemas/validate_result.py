"""loop-validate-result/v1 — typed validate boundary outcome."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_VALIDATE_RESULT = "loop-validate-result/v1"


class ValidateResult(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_VALIDATE_RESULT)
    schema_id: str
    valid: bool
    errors: list[str] = Field(default_factory=list)
    diagnostic_codes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _schema_id(cls, value: str) -> str:
        if value != SCHEMA_LOOP_VALIDATE_RESULT:
            raise ValueError(f"unsupported validate result schema: {value!r}")
        return value
