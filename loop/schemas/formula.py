"""Pydantic schema and YAML loader for decompose-formula/v1."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field, ValidationError


class FormulaStep(BaseModel):
    """Atomic step definition in a decompose formula."""

    title: str
    goal_template: str
    typical_files_pattern: list[str] = Field(default_factory=list)
    verify_hints: list[str] = Field(default_factory=list)


class DecomposeFormula(BaseModel):
    """Schema decompose-formula/v1 for reusable DECOMPOSE formulas."""

    schema_version: Literal["decompose-formula/v1"] = Field(
        default="decompose-formula/v1", alias="schema"
    )
    id: str
    description: str
    default_level: str = "L2"
    steps: list[FormulaStep] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


def load_formula(path: str | Path) -> DecomposeFormula:
    """Load and validate a decompose formula YAML file.

    Raises:
        ValueError: If file cannot be read, YAML is invalid, or schema validation fails.
    """
    file_path = Path(path)
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise ValueError(f"Formula file at {file_path} must contain a YAML mapping/object")
        return DecomposeFormula.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as err:
        raise ValueError(f"Failed to load formula from {file_path}: {err}") from err
