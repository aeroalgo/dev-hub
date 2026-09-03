"""Tests for bin/hub-link harness compatibility."""

import os
import subprocess
import sys
from pathlib import Path


def test_hub_link_idempotent(tmp_path: Path):
    """Verify bin/hub-link creates valid links in product and can run repeatedly without error."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "fake_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    # First run
    res1 = subprocess.run([str(hub_link_bin), "--mode=full", str(product_dir)], env=env, capture_output=True, text=True)
    assert res1.returncode == 0, f"First hub-link failed: {res1.stderr}"

    # Verify .claude/hooks exists in product
    product_hooks = product_dir / ".claude" / "hooks"
    assert product_hooks.exists()

    # Second run (idempotent)
    res2 = subprocess.run([str(hub_link_bin), "--mode=full", str(product_dir)], env=env, capture_output=True, text=True)
    assert res2.returncode == 0, f"Second hub-link failed: {res2.stderr}"


def test_product_hooks_resolve(tmp_path: Path):
    """Verify product .claude/hooks resolves to canonical harness/hooks."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "fake_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=full", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0

    product_hooks = product_dir / ".claude" / "hooks"
    resolved_hooks = product_hooks.resolve()
    expected_hooks = (hub_dir / "harness" / "hooks").resolve()

    assert resolved_hooks == expected_hooks, f"Expected {expected_hooks}, got {resolved_hooks}"


def test_product_settings_hook_paths_resolve(tmp_path: Path):
    """Verify settings.json hook paths via .claude/hooks work in a linked product."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "fake_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=full", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0

    settings_path = product_dir / ".claude" / "settings.json"
    assert settings_path.is_symlink()

    import json

    settings = json.loads(settings_path.read_text())
    hook_commands = []
    for event_hooks in settings.get("hooks", {}).values():
        for block in event_hooks:
            for hook in block.get("hooks", []):
                cmd = hook.get("command", "")
                if "python3" in cmd and ".claude/hooks/" in cmd:
                    hook_commands.append(cmd)

    assert hook_commands, "settings.json must reference .claude/hooks paths"

    for cmd in hook_commands:
        rel = cmd.split('"$CLAUDE_PROJECT_DIR/')[1].split('"')[0]
        hook_file = product_dir / rel
        assert hook_file.exists(), f"Product hook missing: {hook_file} (from {cmd})"


def test_product_full_links_resolve_to_harness_sot(tmp_path: Path):
    """Verify full mode links .agents/skills and .claude/{commands,skills,rules} to canonical harness SoT."""
    hub_dir = Path(__file__).resolve().parents[2]
    product_dir = tmp_path / "fake_product"
    product_dir.mkdir()

    env = dict(os.environ, DEV_HUB=str(hub_dir))
    hub_link_bin = hub_dir / "bin" / "hub-link"

    res = subprocess.run([str(hub_link_bin), "--mode=full", str(product_dir)], env=env, capture_output=True, text=True)
    assert res.returncode == 0, f"hub-link failed: {res.stderr}"

    # .agents/skills resolves to harness/skills
    prod_skills = product_dir / ".agents" / "skills"
    assert prod_skills.exists(), "Product .agents/skills must exist"
    assert prod_skills.is_symlink(), "Product .agents/skills must be a symlink"
    assert prod_skills.resolve() == (hub_dir / "harness" / "skills").resolve()

    # Whole .agents must NOT be linked directly as a single symlink
    assert not (product_dir / ".agents").is_symlink(), ".agents itself should be a dir containing symlinks, not a symlink itself"

    # .claude/commands resolves to harness/claude/commands
    prod_commands = product_dir / ".claude" / "commands"
    assert prod_commands.exists()
    assert prod_commands.resolve() == (hub_dir / "harness" / "claude" / "commands").resolve()

    # .claude/skills resolves to harness/claude/skills
    prod_claude_skills = product_dir / ".claude" / "skills"
    assert prod_claude_skills.exists()
    assert prod_claude_skills.resolve() == (hub_dir / "harness" / "claude" / "skills").resolve()

    # .claude/rules resolves to harness/claude/rules
    prod_claude_rules = product_dir / ".claude" / "rules"
    assert prod_claude_rules.exists()
    assert prod_claude_rules.resolve() == (hub_dir / "harness" / "claude" / "rules").resolve()


def test_no_dual_sot_in_hub_layout():
    """TM-006: Hub layout has single SoT in harness/ — .claude and .agents are symlinks, not duplicate directories."""
    hub_dir = Path(__file__).resolve().parents[2]

    # .claude/commands, skills, rules must be symlinks
    for rel in [".claude/commands", ".claude/skills", ".claude/rules", ".agents/skills"]:
        p = hub_dir / rel
        assert p.is_symlink(), f"{rel} must be a symlink in hub layout"
        # resolved target must be within harness/
        resolved = p.resolve()
        assert str(resolved).startswith(str((hub_dir / "harness").resolve())), f"{rel} must resolve into harness/"
