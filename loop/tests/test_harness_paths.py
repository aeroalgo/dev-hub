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
