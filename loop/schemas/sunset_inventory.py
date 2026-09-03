"""loop-sunset-inventory/v1 — typed sunset inventory report contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_LOOP_SUNSET_INVENTORY = "loop-sunset-inventory/v1"

SunsetKind = Literal["A", "B", "C", "I"]
SunsetMark = Literal["REPLACE"]


class SunsetItem(BaseModel):
    kind: SunsetKind
    symbol: str
    path: str
    start_line: int
    end_line: int
    excerpt: str
    mark: SunsetMark
    role: str
    notes: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("excerpt")
    @classmethod
    def _validate_excerpt_length(cls, value: str) -> str:
        lines = value.splitlines()
        if len(lines) > 40:
            raise ValueError(f"excerpt exceeds maximum budget of 40 lines (got {len(lines)})")
        return value

    @field_validator("symbol", "path", "role", mode="before")
    @classmethod
    def _strip_non_empty_str(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("field cannot be empty")
            return stripped
        return value


class SunsetReport(BaseModel):
    schema_version: str = Field(alias="schema", default=SCHEMA_LOOP_SUNSET_INVENTORY)
    boundary_id: str
    new_sot: str
    forbidden_for_parent: list[str] = Field(default_factory=list)
    diagnostic_codes: list[str] = Field(default_factory=list)
    ok: bool = True
    items: list[SunsetItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("schema_version")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        if value != SCHEMA_LOOP_SUNSET_INVENTORY:
            raise ValueError(f"unsupported sunset inventory schema: {value!r}")
        return value

    @field_validator("boundary_id", "new_sot", mode="before")
    @classmethod
    def _strip_non_empty(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("field cannot be empty")
            return stripped
        return value
