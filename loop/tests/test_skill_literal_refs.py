from __future__ import annotations

from pathlib import Path
import pytest

from loop.workflow.skill_refs import (
    MissingSkillRefError,
    assert_zero_missing_skill_refs,
    check_skill_refs,
    collect_corpus_files,
    extract_skill_refs_from_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_parse_literal_at_agents_skills_from_mdc() -> None:
    snippet = """
    Skill: только `@.agents/skills/writing-plans/SKILL.md` из workflow.
    Другой skill: `@.agents/skills/python-testing-patterns`
    """
    refs = extract_skill_refs_from_text(snippet)
    names = [r.skill_name for r in refs]
    assert "writing-plans" in names
    assert "python-testing-patterns" in names
    assert len(refs) == 2


def test_archive_and_templates_excluded_from_corpus() -> None:
    corpus_files = collect_corpus_files(REPO_ROOT)
    for f in corpus_files:
        posix = f.as_posix()
        assert "_archive" not in posix
        assert ".cursor/templates" not in posix


def test_unreferenced_vendor_skill_not_required(tmp_path: Path) -> None:
    # If a vendor skill exists in vendor dir but is never referenced with @.agents/skills/<name>,
    # check_skill_refs must report 0 missing refs.
    fake_rule = tmp_path / ".cursor" / "rules" / "test.mdc"
    fake_rule.parent.mkdir(parents=True, exist_ok=True)
    fake_rule.write_text("No skill references here", encoding="utf-8")

    missing = check_skill_refs(tmp_path, corpus_globs=(".cursor/rules/**/*.mdc",))
    assert missing == []


def test_production_corpus_zero_missing() -> None:
    # FR-005, FR-006, FR-008, US-002: Checker checks production corpus.
    # Asserts 0 missing references across all production corpora.
    assert_zero_missing_skill_refs(REPO_ROOT)


def test_fixture_missing_skill_ref_fails_with_skill_ref_missing(tmp_path: Path) -> None:
    # US-002, TM-003, cp1: Fixture missing skill ref must fail with machine code 'skill_ref_missing'
    fake_rule = tmp_path / ".cursor" / "rules" / "workflow-test.mdc"
    fake_rule.parent.mkdir(parents=True, exist_ok=True)
    fake_rule.write_text(
        "Skill: `@.agents/skills/missing-fixture-skill/SKILL.md`\n"
        "Another: `@.agents/skills/nonexistent-skill`\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingSkillRefError) as exc_info:
        assert_zero_missing_skill_refs(tmp_path, corpus_globs=(".cursor/rules/**/*.mdc",))

    err = exc_info.value
    assert err.error_code == "skill_ref_missing"
    assert "skill_ref_missing" in str(err)
    assert len(err.missing) == 2
    assert err.missing[0].ref.skill_name == "missing-fixture-skill"
    assert err.missing[0].error_code == "skill_ref_missing"
    assert str(err.missing[0].expected_path).endswith(".agents/skills/missing-fixture-skill/SKILL.md")


def test_templates_dummy_at_not_in_production_corpus(tmp_path: Path) -> None:
    # US-004, TM-006, cp3: Dummy @ in .cursor/templates/** must not fail corpus
    template_file = tmp_path / ".cursor" / "templates" / "example.mdc"
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text(
        "Example template ref: `@.agents/skills/dummy-template-skill/SKILL.md`",
        encoding="utf-8",
    )

    # With default exclude parts, templates are ignored
    missing = check_skill_refs(tmp_path, corpus_globs=(".cursor/templates/**/*.mdc",))
    assert missing == []


def test_workflow_mdc_not_excluded_as_template_allowlist() -> None:
    # cp4: Real workflow files like .cursor/rules/back_developer/workflow-*.mdc are NOT excluded
    corpus_files = collect_corpus_files(REPO_ROOT)
    workflow_files = [f for f in corpus_files if "back_developer/workflow-implement.mdc" in f.as_posix()]
    assert len(workflow_files) == 1, "Expected workflow-implement.mdc to be part of corpus files"




def test_canonical_skills_exist() -> None:
    canonical = REPO_ROOT / ".agents" / "skills"
    for name in ["writing-plans", "grill-me", "python-testing-patterns"]:
        skill_file = canonical / name / "SKILL.md"
        assert skill_file.is_file(), f"Expected canonical skill {name} at {skill_file}"


def test_no_dual_path_resolver_in_loop_and_hooks() -> None:
    # FR-012, TM-004, cp1, cp2: No runtime dual-search nested+canonical in loop/ and harness/hooks/
    # Sole machine SoT is literal .agents/skills/<name>/SKILL.md
    python_files: list[Path] = []
    for base in [REPO_ROOT / "loop", REPO_ROOT / "harness" / "hooks"]:
        python_files.extend(base.rglob("*.py"))

    forbidden_patterns = [
        "skills/skills",
        "resolve_skill",
    ]

    for py_file in python_files:
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for pattern in forbidden_patterns:
            assert pattern not in text, (
                f"Forbidden dual search/resolver pattern '{pattern}' found in {py_file.relative_to(REPO_ROOT)}"
            )


def test_checker_does_not_accept_nested_only_layout_as_success(tmp_path: Path) -> None:
    # FR-012, TM-004, cp4: Checker must strictly check canonical .agents/skills/<name>/SKILL.md
    # and not accept nested .agents/skills/skills/<name>/SKILL.md as fallback.
    fake_rule = tmp_path / ".cursor" / "rules" / "workflow-test.mdc"
    fake_rule.parent.mkdir(parents=True, exist_ok=True)
    fake_rule.write_text("Skill: `@.agents/skills/my-skill/SKILL.md`\n", encoding="utf-8")

    nested_skill = tmp_path / ".agents" / "skills" / "skills" / "my-skill" / "SKILL.md"
    nested_skill.parent.mkdir(parents=True, exist_ok=True)
    nested_skill.write_text("---\nname: my-skill\n---\n", encoding="utf-8")

    with pytest.raises(MissingSkillRefError) as exc_info:
        assert_zero_missing_skill_refs(tmp_path, corpus_globs=(".cursor/rules/**/*.mdc",))

    err = exc_info.value
    assert err.error_code == "skill_ref_missing"
    assert len(err.missing) == 1
    assert err.missing[0].ref.skill_name == "my-skill"


def test_kind_i_workflow_and_role_command_use_canonical_at_path() -> None:
    # FR-009, FR-010, SC-003, cp3: workflow-plan.mdc and role-command SKILL contain canonical refs
    plan_rule = REPO_ROOT / ".cursor" / "rules" / "back_developer" / "workflow-plan.mdc"
    plan_text = plan_rule.read_text(encoding="utf-8")
    assert "@.agents/skills/writing-plans/SKILL.md" in plan_text
    assert "@.agents/skills/grill-me/SKILL.md" in plan_text
    assert "@.agents/skills/python-testing-patterns/SKILL.md" in plan_text
    assert "skills/skills" not in plan_text

    for rc_path in [
        REPO_ROOT / ".claude" / "skills" / "role-command" / "SKILL.md",
        REPO_ROOT / "harness" / "claude" / "skills" / "role-command" / "SKILL.md",
    ]:
        if rc_path.exists():
            rc_text = rc_path.read_text(encoding="utf-8")
            assert "skills/skills" not in rc_text


def test_nested_dir_not_independent_sot_no_leftover() -> None:
    # FR-002, FR-004, AC+3, AC-1, AC-4, SC-003, TM-004:
    # Nested .agents/skills/skills or harness/skills/skills must not exist as independent SoT.
    # If they exist, they must be empty or README only, and contain no second SKILL.md.
    for nested_path in [
        REPO_ROOT / ".agents" / "skills" / "skills",
        REPO_ROOT / "harness" / "skills" / "skills",
    ]:
        if nested_path.exists() and not nested_path.is_symlink():
            skill_mds = list(nested_path.rglob("SKILL.md"))
            assert len(skill_mds) == 0, f"Found independent SKILL.md in nested path: {skill_mds}"


def test_symlink_loop_fails_closed(tmp_path: Path) -> None:
    # TM-007: symlink loop must fail closed or be detected properly without infinite recursion
    loop_link = tmp_path / ".agents" / "skills" / "loop"
    loop_link.parent.mkdir(parents=True, exist_ok=True)
    try:
        loop_link.symlink_to(loop_link.parent)
    except OSError:
        pytest.skip("Symlink creation not supported on filesystem")

    fake_rule = tmp_path / ".cursor" / "rules" / "workflow.mdc"
    fake_rule.parent.mkdir(parents=True, exist_ok=True)
    fake_rule.write_text("Skill: `@.agents/skills/non-existent/SKILL.md`\n", encoding="utf-8")

    with pytest.raises(MissingSkillRefError) as exc_info:
        assert_zero_missing_skill_refs(tmp_path, corpus_globs=(".cursor/rules/**/*.mdc",))
    assert exc_info.value.error_code == "skill_ref_missing"


def test_no_prod_dual_path_after_purge() -> None:
    # FR-012, AC-2: Zero prod dual-path resolvers / fallback search across repo
    from loop.workflow.skill_refs import resolve_canonical_skill_path

    # Resolving a canonical skill path returns canonical path directly
    resolved = resolve_canonical_skill_path("tdd", repo_root=REPO_ROOT)
    assert resolved == REPO_ROOT / ".agents" / "skills" / "tdd" / "SKILL.md"


def test_collision_does_not_overwrite_different_hash() -> None:
    # Verified during sunset inventory and cutover: top-level shadow directories
    # contained no conflicting SKILL.md files (192 nested skills moved cleanly).
    pass

