"""Tests for the command-first workflow prompt scope."""
from __future__ import annotations

from pathlib import Path

import pytest

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
    assert scope.workflow_file is None
    rendered = render_prompt_scope(scope)
    assert rendered.startswith("COMMAND: BACK IMPLEMENT\n")
    assert "HARD READ" in rendered
    assert "цепочку связанных файлов" in rendered
    assert "workflow-implement.mdc" not in rendered
    assert "AGENTS.md" not in rendered
    assert "CLAUDE.md" in rendered


def test_scope_normalizes_integration_alias_and_ignores_step_suffix() -> None:
    from prompt_builder import build_prompt_scope

    scope = build_prompt_scope(
        ROOT,
        command="INTEGRATION QA @e16",
        projection={"epic": "T-test", "step": "e16"},
    )

    assert scope.command == "INTEG QA"
    assert scope.role == "INTEG"
    assert scope.workflow_file is None


def test_scope_does_not_resolve_workflow_paths_from_pack(tmp_path: Path) -> None:
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
    assert scope.pack_id is None
    assert scope.diagnostics == ()
    assert "scope diagnostics" not in render_prompt_scope(scope)


def test_scope_without_phase_is_explicitly_unknown(tmp_path: Path) -> None:
    from prompt_builder import build_prompt_scope

    scope = build_prompt_scope(tmp_path, projection={"step": "s01"})

    assert scope.command == "UNKNOWN"
    assert scope.workflow_file is None


def test_scope_selects_codex_entrypoint_without_loading_claude() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(ROOT, command="BACK QA", runtime="codex")

    rendered = render_prompt_scope(scope)
    assert "entrypoint: `AGENTS.md`" in rendered
    assert "CLAUDE.md" not in rendered
    assert "mainrule.mdc" in rendered


def test_scope_keeps_only_current_command_contract() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(ROOT, command="BACK QA", runtime="claude-code")

    rendered = render_prompt_scope(scope)
    assert "role: `BACK`" in rendered
    assert "phase: `QA`" in rendered
    assert "FRONT" not in rendered
    assert "INTEG" not in rendered
    assert "IMPLEMENT" not in rendered


_ROLE_COMMANDS = [
    *[
        f"BACK {mode}"
        for mode in (
            "VAN",
            "PLAN",
            "CLARIFY",
            "DECOMPOSE",
            "ANALYZE",
            "CREATIVE",
            "IMPLEMENT",
            "AUDIT",
            "QA",
            "ARCHIVE NOW",
            "TASK",
            "BUGFIX",
            "REFACTOR",
            "SECURITY",
            "SECURITY PLAN",
            "SECURITY DECOMPOSE",
            "ROADMAP MERGE",
            "RECONCILE",
            "JANITOR",
        )
    ],
    *[
        f"FRONT {mode}"
        for mode in (
            "VAN",
            "PLAN",
            "CLARIFY",
            "ANALYZE",
            "ROADMAP MERGE",
            "DECOMPOSE",
            "CREATIVE",
            "IMPLEMENT",
            "AUDIT",
            "TASK",
            "BUGFIX",
            "REFACTOR",
            "ARCHIVE NOW",
            "QA",
            "SECURITY",
            "SECURITY PLAN",
            "SECURITY DECOMPOSE",
        )
    ],
    *[
        f"INTEG {mode}"
        for mode in (
            "VAN",
            "GAP",
            "GAP CLOSE",
            "PLAN",
            "CLARIFY",
            "ANALYZE",
            "ROADMAP MERGE",
            "DECOMPOSE",
            "CREATIVE",
            "IMPLEMENT",
            "AUDIT",
            "TASK",
            "BUGFIX",
            "REFACTOR",
            "ARCHIVE NOW",
            "QA",
            "SECURITY",
            "SECURITY PLAN",
            "SECURITY DECOMPOSE",
        )
    ],
]


@pytest.mark.parametrize("command", _ROLE_COMMANDS)
def test_scope_isolated_for_every_role_command(command: str) -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(ROOT, command=command, runtime="claude-code")
    rendered = render_prompt_scope(scope)
    role = command.split(maxsplit=1)[0]
    other_roles = {"BACK", "FRONT", "INTEG"} - {role}

    assert scope.command == command
    assert f"COMMAND: {command}\n" in rendered
    assert f"role: `{role}`" in rendered
    assert "entrypoint: `CLAUDE.md`" in rendered
    assert "workflow-" not in rendered
    assert all(other not in rendered for other in other_roles)
