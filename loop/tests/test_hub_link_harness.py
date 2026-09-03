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
