"""Pydantic schema for Janitor entropy audit report (janitor-report/v1)."""

from __future__ import annotations

import warnings
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

warnings.filterwarnings("ignore", message=".*shadows an attribute in parent.*")

JANITOR_REPORT_SCHEMA = "janitor-report/v1"


class JanitorFinding(BaseModel):
    """Entropy audit finding."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    actionable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class JanitorSummary(BaseModel):
    """Summary of findings count by category."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    total_findings: int = 0
    categories_count: dict[str, int] = Field(default_factory=dict)


class JanitorReport(BaseModel):
    """Schema for JanitorReport entropy audit report."""

    model_config = {"protected_namespaces": (), "extra": "allow"}

    schema: Literal["janitor-report/v1"] = "janitor-report/v1"
    cwd: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    findings: list[JanitorFinding] = Field(default_factory=list)
    summary: JanitorSummary = Field(default_factory=JanitorSummary)

    @field_validator("schema", mode="before")
    @classmethod
    def _validate_schema(cls, v: Any) -> str:
        if v != JANITOR_REPORT_SCHEMA:
            raise ValueError(f"invalid schema version: {v}")
        return str(v)
