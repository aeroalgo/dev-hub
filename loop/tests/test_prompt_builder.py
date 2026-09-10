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
    assert "canonical hot path" in rendered
    assert "harness/cursor/rules/back_developer/workflow-implement.mdc#Hot path" in rendered
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
    (tmp_path / "dev-hub.project.yaml").write_text(
        "schema: dev-hub-project/v1\n"
        "workflow_pack: does-not-exist\n"
        "targets:\n"
        "  backend:\n"
        "    root: .\n"
        "    profile: python\n",
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


def test_scope_limits_skills_to_selected_workflow_refs() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    rendered = render_prompt_scope(
        build_prompt_scope(ROOT, command="BACK IMPLEMENT", runtime="codex")
    )

    assert "## SKILLS LOAD POLICY (HARD)" in rendered
    assert "локального `.agents/skills/`" in rendered
    assert "автоматический каталог" in rendered
    assert "skills.impl" in rendered
    assert "skills.design" in rendered
    assert "no skill read" in rendered
    assert "Available skills" not in rendered


def test_scope_uses_recursive_chain_only_for_recursive_workflow_modes() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    implement = render_prompt_scope(
        build_prompt_scope(ROOT, command="BACK IMPLEMENT", runtime="codex")
    )
    plan = render_prompt_scope(
        build_prompt_scope(ROOT, command="BACK PLAN", runtime="codex")
    )

    assert "canonical hot path" in implement
    assert "не рекурсивно" in implement
    assert "harness/cursor/rules/back_developer/workflow-implement.mdc#Hot path" in implement
    assert "isolation_rules/_lean/implement.mdc" in implement
    assert "связанные @-ссылки" in plan

    refactor_plan = render_prompt_scope(
        build_prompt_scope(ROOT, command="BACK PLAN REFACTOR", runtime="codex")
    )
    assert "COMMAND: BACK PLAN REFACTOR" in refactor_plan
    assert "phase: `PLAN REFACTOR`" in refactor_plan
    assert "связанные @-ссылки" in refactor_plan


def test_composite_refactor_plan_keeps_command_but_uses_plan_step() -> None:
    from prompt_builder import resolve_session_identity

    identity = resolve_session_identity(
        None,
        None,
        {"phase": "BACK PLAN REFACTOR", "epic": "T-test"},
    )

    assert identity.command == "BACK PLAN REFACTOR"
    assert identity.phase == "PLAN REFACTOR"
    assert identity.step == "PLAN"


def test_codex_prompt_requires_native_collaboration_for_gates() -> None:
    from context_loop import build_prompt

    prompt = build_prompt(
        ROOT,
        command="BACK IMPLEMENT",
        runtime="codex",
        projection={"phase": "BACK IMPLEMENT", "epic": "T-test", "step": "s01"},
        load_now=[],
    )

    assert "CODEX NATIVE COLLABORATION" in prompt
    assert "spawn_agent" in prompt
    assert "gate-repair" in prompt
    assert "multi_agent_v1_spawn_agent" not in prompt
    assert "не является частью обычного IMPLEMENT" in prompt
    assert "RECONCILE REQUIRED" not in prompt


def test_claude_prompt_uses_shared_policy_and_claude_transport() -> None:
    from context_loop import build_prompt

    prompt = build_prompt(
        ROOT,
        command="BACK QA",
        runtime="claude-code",
        projection={"phase": "BACK QA", "epic": "T-test", "step": "QA"},
        load_now=[],
    )

    assert "SHARED GATE COLLABORATION CONTRACT — QA" in prompt
    assert "loop-qa-outcome/v1" in prompt or "QA outcome classifier" in prompt
    assert "BUGFIX" in prompt
    assert "gate-repair → full suite → verify-qa" not in prompt
    assert "CLAUDE CODE COLLABORATION ADAPTER" in prompt
    assert "Agent" in prompt
    assert "spawn_agent" not in prompt

def test_scope_selects_dsh_native_entrypoint_and_tool_dialect() -> None:
    from prompt_builder import build_prompt_scope, render_prompt_scope

    scope = build_prompt_scope(ROOT, command="BACK IMPLEMENT", runtime="dsh")

    rendered = render_prompt_scope(scope)
    assert scope.runtime == "dsh"
    assert scope.entrypoint == "AGENTS.md"
    assert "entrypoint: `AGENTS.md`" in rendered
    assert "native DSH tool `read`" in rendered
    assert "SKILL.md" in rendered
    assert "Claude Code tools `Read`" in rendered
    assert "CLAUDE.md" not in rendered


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
            "PLAN REFACTOR",
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
    phase = command.split(maxsplit=1)[1] if " " in command else ""
    if phase in {"IMPLEMENT", "TASK", "BUGFIX", "REFACTOR"}:
        role_dir = {
            "BACK": "back_developer",
            "FRONT": "front_developer",
            "INTEG": "integration_developer",
        }[role]
        assert (
            f"harness/cursor/rules/{role_dir}/workflow-{phase.lower()}.mdc#Hot path"
            in rendered
        )
    else:
        assert "workflow-" not in rendered
    assert all(other not in rendered for other in other_roles)
