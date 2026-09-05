"""Integration tests for harness paths and symlinks."""

import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_symlink_hooks_points_to_harness():
    """Verify .claude/hooks is a symlink pointing to harness/hooks (or ../harness/hooks)."""
    hooks_path = ROOT / ".claude" / "hooks"
    assert hooks_path.is_symlink(), ".claude/hooks must be a symlink"
    target = hooks_path.readlink()
    assert "harness/hooks" in str(target)


def test_symlink_commands_points_to_harness():
    """TM-001: Verify .claude/commands is a symlink pointing to harness/claude/commands."""
    commands_path = ROOT / ".claude" / "commands"
    assert commands_path.is_symlink(), ".claude/commands must be a symlink"
    target = commands_path.readlink()
    assert "harness/claude/commands" in str(target)


def test_symlink_skills_points_to_harness():
    """TM-001: Verify .claude/skills is a symlink pointing to harness/claude/skills."""
    skills_path = ROOT / ".claude" / "skills"
    assert skills_path.is_symlink(), ".claude/skills must be a symlink"
    target = skills_path.readlink()
    assert "harness/claude/skills" in str(target)
    assert (ROOT / "harness" / "claude" / "skills" / "role-command" / "SKILL.md").exists()
    assert (ROOT / ".claude" / "skills" / "role-command" / "SKILL.md").exists()


def test_symlink_rules_points_to_harness():
    """TM-001: Verify .claude/rules is a symlink pointing to harness/claude/rules."""
    rules_path = ROOT / ".claude" / "rules"
    assert rules_path.is_symlink(), ".claude/rules must be a symlink"
    target = rules_path.readlink()
    assert "harness/claude/rules" in str(target)
    assert (ROOT / "harness" / "claude" / "rules" / "language.md").exists()
    assert (ROOT / ".claude" / "rules" / "language.md").exists()


def test_symlink_agents_skills_points_to_harness():
    """TM-001 / TM-002: Verify .agents/skills is a symlink pointing to harness/skills (SoT)."""
    agents_skills = ROOT / ".agents" / "skills"
    assert agents_skills.is_symlink(), ".agents/skills must be a symlink"
    assert agents_skills.resolve() == (ROOT / "harness" / "skills").resolve()
    assert (ROOT / "harness" / "skills").is_dir()
    assert (ROOT / ".agents" / ".skill-lock.json").is_file()
    assert not (ROOT / ".agents" / ".skill-lock.json").is_symlink()
    # TM-002 sample SKILL.md reachable via both paths
    assert (ROOT / "harness" / "skills" / "product-discovery" / "SKILL.md").exists()
    assert (ROOT / ".agents" / "skills" / "product-discovery" / "SKILL.md").exists()


def test_harness_import_smoke():
    """Verify harness.hooks package can be imported directly."""
    import harness.hooks
    assert harness.hooks is not None


def test_stop_gate_reachable_via_symlink():
    """Verify stop-gate scripts are reachable through both harness/hooks and .claude/hooks."""
    harness_stop_gate = ROOT / "harness" / "hooks" / "agent_policy.py"
    claude_stop_gate = ROOT / ".claude" / "hooks" / "agent_policy.py"

    assert harness_stop_gate.exists(), "harness/hooks/agent_policy.py missing"
    assert claude_stop_gate.exists(), ".claude/hooks/agent_policy.py missing via symlink"
