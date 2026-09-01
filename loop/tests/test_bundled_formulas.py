"""Tests for bundled formulas in loop/formulas/."""

from pathlib import Path
import pytest
from loop.schemas.formula import load_formula, DecomposeFormula

FORMULAS_DIR = Path("loop/formulas")

def test_hooks_epic_loads():
    formula_path = FORMULAS_DIR / "hooks-epic.yaml"
    assert formula_path.exists(), "hooks-epic.yaml file must exist"
    formula = load_formula(formula_path)
    assert formula.id == "hooks-epic"
    assert len(formula.steps) >= 5

def test_all_bundled_formulas_valid():
    yaml_files = list(FORMULAS_DIR.glob("*.yaml"))
    assert len(yaml_files) >= 3, "Should have at least 3 bundled formula YAML files"

    for yaml_file in yaml_files:
        formula = load_formula(yaml_file)
        assert isinstance(formula, DecomposeFormula)
        assert formula.id is not None
        assert formula.schema_version == "decompose-formula/v1"

def test_formulas_have_steps_with_content():
    yaml_files = list(FORMULAS_DIR.glob("*.yaml"))
    for yaml_file in yaml_files:
        formula = load_formula(yaml_file)
        assert len(formula.steps) >= 3, f"Formula {formula.id} should have at least 3 steps"
        for step in formula.steps:
            assert step.goal_template, f"Step '{step.title}' in {formula.id} must have a non-empty goal_template"
            assert step.typical_files_pattern, f"Step '{step.title}' in {formula.id} must have typical_files_pattern"

def test_formula_step_goal_template_has_placeholder():
    yaml_files = list(FORMULAS_DIR.glob("*.yaml"))
    for yaml_file in yaml_files:
        formula = load_formula(yaml_file)
        for step in formula.steps:
            assert "{" in step.goal_template and "}" in step.goal_template, (
                f"Step '{step.title}' in {formula.id} goal_template should contain dynamic placeholders (e.g. {{epic_name}})"
            )
