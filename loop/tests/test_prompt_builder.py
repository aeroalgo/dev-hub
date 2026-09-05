"""Tests for the command-first workflow prompt scope."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scope_routes_one_workflow_for_current_command() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(
        ROOT,
        projection={
            "phase": "BACK IMPLEMENT",
            "epic": "T-test",
            "step": "s01",
        },
    )

    assert scope.command == "BACK IMPLEMENT"
    assert scope.workflow_file == ".cursor/rules/back_developer/workflow-implement.mdc"
    rendered = render_prompt_scope(scope)
    assert rendered.startswith("COMMAND: BACK IMPLEMENT\n")
    assert "HARD READ" in rendered
    assert "all linked" not in rendered
    assert "цепочку связанных файлов" in rendered
    assert "front_developer" not in rendered


def test_scope_normalizes_integration_alias_and_ignores_step_suffix() -> None:
    from prompt_builder import build_prompt_scope

    scope = build_prompt_scope(
        ROOT,
        command="INTEGRATION QA @e16",
        projection={"epic": "T-test", "step": "e16"},
    )

    assert scope.command == "INTEG QA"
    assert scope.role == "INTEG"
    assert scope.workflow_file == ".cursor/rules/integration_developer/workflow-qa.mdc"


def test_scope_falls_back_without_pack_failure(tmp_path: Path) -> None:
    (tmp_path / "project.yaml").write_text(
        "workflow_pack: does-not-exist\n",
        encoding="utf-8",
    )

    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(
        tmp_path,
        projection={"phase": "BACK IMPLEMENT", "step": "s01"},
    )

    assert scope.command == "BACK IMPLEMENT"
    assert scope.workflow_file is None
    assert "invalid_workflow_pack" in scope.diagnostics
    assert "scope diagnostics" in render_prompt_scope(scope)


def test_scope_without_phase_is_explicitly_unknown(tmp_path: Path) -> None:
    from prompt_builder import build_prompt_scope

    scope = build_prompt_scope(tmp_path, projection={"step": "s01"})

    assert scope.command == "UNKNOWN"
    assert scope.workflow_file is None
