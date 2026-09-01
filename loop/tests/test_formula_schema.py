"""Tests for loop/schemas/formula.py."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from loop.schemas.formula import DecomposeFormula, FormulaStep, load_formula


def test_decompose_formula_valid():
    data = {
        "schema": "decompose-formula/v1",
        "id": "test-formula",
        "description": "Test formula description",
        "steps": [],
    }
    formula = DecomposeFormula.model_validate(data)
    assert formula.schema_version == "decompose-formula/v1"
    assert formula.id == "test-formula"
    assert formula.description == "Test formula description"
    assert formula.default_level == "L2"
    assert formula.steps == []


def test_decompose_formula_missing_required():
    data = {
        "schema": "decompose-formula/v1",
        "id": "test-formula",
    }
    with pytest.raises(ValidationError):
        DecomposeFormula.model_validate(data)


def test_load_formula_valid_file(tmp_path: Path):
    yaml_content = """
schema: "decompose-formula/v1"
id: "crud-feature"
description: "Standard CRUD feature formula"
default_level: "L3"
steps:
  - title: "API schema & endpoint"
    goal_template: "Implement API endpoints for {feature}"
    typical_files_pattern:
      - "app/api/{feature}.py"
    verify_hints:
      - "pytest tests/api/test_{feature}.py"
"""
    formula_file = tmp_path / "crud.yaml"
    formula_file.write_text(yaml_content, encoding="utf-8")

    formula = load_formula(formula_file)
    assert formula.id == "crud-feature"
    assert formula.default_level == "L3"
    assert len(formula.steps) == 1
    assert formula.steps[0].title == "API schema & endpoint"
    assert formula.steps[0].typical_files_pattern == ["app/api/{feature}.py"]


def test_load_formula_invalid_yaml(tmp_path: Path):
    invalid_file = tmp_path / "invalid_formula.yaml"
    invalid_file.write_text("schema: [invalid yaml content", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_formula(invalid_file)

    assert str(invalid_file) in str(exc_info.value)


def test_formula_step_fields():
    step_data = {
        "title": "Database Migration",
        "goal_template": "Create migration for {entity}",
        "typical_files_pattern": ["migrations/*.py"],
        "verify_hints": ["alembic upgrade head"],
    }
    step = FormulaStep.model_validate(step_data)
    assert step.title == "Database Migration"
    assert step.goal_template == "Create migration for {entity}"
    assert step.typical_files_pattern == ["migrations/*.py"]
    assert step.verify_hints == ["alembic upgrade head"]
