"""Tests for Step s03: Kind I — mainrule/role-command current entrypoint only (FR-006, US-003, SC-003, TM-006)."""

from __future__ import annotations

from pathlib import Path
import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_mainrule_no_unconditional_claude_md_for_codex():
    """TM-006 / US-003 / FR-006: mainrule.mdc must not force unconditional Read of CLAUDE.md for all runtimes."""
    mainrule_path = _repo_root() / ".cursor" / "rules" / "mainrule.mdc"
    assert mainrule_path.is_file(), f"Missing {mainrule_path}"
    content = mainrule_path.read_text(encoding="utf-8")

    # Forbidden unconditional phrase
    assert "Read корневого CLAUDE.md" not in content
    # Required runtime entrypoint prompt scope reference
    assert "entrypoint текущего runtime" in content
    assert "CLAUDE.md" in content
    assert "AGENTS.md" in content


def test_role_command_skill_uses_runtime_entrypoint():
    """FR-006 / SC-003: role-command SKILL copies must use runtime entrypoint, not hardcoded CLAUDE for Codex."""
    targets = [
        _repo_root() / ".claude" / "skills" / "role-command" / "SKILL.md",
        _repo_root() / "harness" / "claude" / "skills" / "role-command" / "SKILL.md",
    ]
    for skill_path in targets:
        assert skill_path.is_file(), f"Missing {skill_path}"
        content = skill_path.read_text(encoding="utf-8")
        assert "Read корневого CLAUDE.md" not in content
        assert "entrypoint текущего runtime" in content
        assert "AGENTS.md" in content


def test_rg_policy_zero_unconditional_claude_hard():
    """TM-006 / AC-3: Policy check — 0 unconditional 'Read корневого CLAUDE.md' in instruction surfaces."""
    surfaces = [
        _repo_root() / ".cursor" / "rules" / "mainrule.mdc",
        _repo_root() / ".claude" / "skills" / "role-command" / "SKILL.md",
        _repo_root() / "harness" / "claude" / "skills" / "role-command" / "SKILL.md",
    ]
    bad_hits = []
    for file_path in surfaces:
        content = file_path.read_text(encoding="utf-8")
        for idx, line in enumerate(content.splitlines(), start=1):
            if "Read корневого CLAUDE.md" in line:
                bad_hits.append(f"{file_path}:{idx}: {line}")

    assert not bad_hits, f"Found unconditional CLAUDE.md HARD hits:\n" + "\n".join(bad_hits)
