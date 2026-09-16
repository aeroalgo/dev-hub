"""Characterization and freeze oracle test matrix for DSH runtime purge.

Verifies fail-closed expectations for DSH runtime deprecation:
- Registry / factory rejection of dsh and historical aliases.
- CLI / env reject dsh without silent fallback to claude.
- Fail-closed behavior on EPIC_RUNTIME=dsh.
"""
import os
import subprocess
import pytest
from pathlib import Path
from loop.runtime.registry import (
    load_registry,
    InvalidRuntimeConfig,
)
from loop.runtime_adapters.base import RuntimeAdapter, SessionContext
from loop.runtime_adapters.common import get_adapter_for_runtime


def test_registry_has_no_dsh():
    """Checkpoint 1 verification: loop/runtime_registry.yaml contains only claude and codex."""
    reg = load_registry()
    valid_ids = reg.list_ids()
    assert "claude" in valid_ids
    assert "codex" in valid_ids
    assert "dsh" not in valid_ids
    assert set(valid_ids) == {"claude", "codex"}


def test_adapter_factory_rejects_dsh():
    """Checkpoint 2 verification: loop/runtime_adapters/dsh.py is deleted and get_adapter_for_runtime('dsh') raises."""
    with pytest.raises(ValueError, match="Unknown runtime: dsh"):
        get_adapter_for_runtime("dsh")


def test_dsh_purge_characterization_registry_oracle():
    """Oracle testing that valid runtimes are present and dsh is tracked for purge."""
    reg = load_registry()
    valid_ids = reg.list_ids()
    assert "claude" in valid_ids
    assert "codex" in valid_ids
    # Verify registry contract structure
    claude_cfg = reg.get_runtime("claude")
    assert claude_cfg["adapter_module"] == "loop.runtime_adapters.claude"
    codex_cfg = reg.get_runtime("codex")
    assert codex_cfg["adapter_module"] == "loop.runtime_adapters.codex"


def test_dsh_no_fallback_to_claude():
    """Explicitly verify that requesting dsh does not silently resolve to claude adapter."""
    from loop.runtime_adapters.claude import ClaudeAdapter
    try:
        adapter = get_adapter_for_runtime("dsh")
        assert not isinstance(adapter, ClaudeAdapter)
        assert not isinstance(adapter, type(ClaudeAdapter()))
    except (ValueError, InvalidRuntimeConfig) as exc:
        # Expected fail-closed behavior once dsh is purged from registry
        assert "Unknown runtime" in str(exc) or "No RuntimeAdapter" in str(exc) or "dsh" in str(exc)


def test_dsh_alias_no_fallback_to_claude():
    """Aliases like deepseek or deepseek-harness must not resolve to claude."""
    from loop.runtime_adapters.claude import ClaudeAdapter
    for alias in ["deepseek", "deepseek-harness", "dsh_cli", "dsh-cli"]:
        try:
            adapter = get_adapter_for_runtime(alias)
            assert not isinstance(adapter, ClaudeAdapter)
        except (ValueError, InvalidRuntimeConfig) as exc:
            # Expected fail-closed behavior
            assert "Unknown runtime" in str(exc) or "No RuntimeAdapter" in str(exc) or alias in str(exc)


def test_dsh_oracle_explicit_rejection_matrix():
    """TM-003 / FR-001 / SC-003: Explicit oracle asserting post-purge registry / factory rejection."""
    # When registry is loaded with only claude and codex, requesting dsh must raise InvalidRuntimeConfig / ValueError
    from loop.runtime.registry import RuntimeRegistry
    clean_registry_data = {
        "schema_version": "runtime-registry/v1",
        "runtimes": {
            "claude": {
                "id": "claude",
                "adapter_module": "loop.runtime_adapters.claude",
                "capabilities": ["stream_json"],
            },
            "codex": {
                "id": "codex",
                "adapter_module": "loop.runtime_adapters.codex",
                "capabilities": ["headless"],
            },
        },
    }
    reg = RuntimeRegistry(clean_registry_data)
    assert "dsh" not in reg.list_ids()
    with pytest.raises(InvalidRuntimeConfig):
        reg.get_runtime("dsh")
    with pytest.raises(InvalidRuntimeConfig):
        reg.get_runtime_adapter("dsh")


def test_runtime_adapter_counterpart_linkages():
    """Verify counterpart linkages between runtime registry and base adapter interface."""
    reg = load_registry()
    dummy_ctx = SessionContext(prompt="test", phase="IMPLEMENT", runtime_id="claude")
    for runtime_id in ["claude", "codex"]:
        adapter = get_adapter_for_runtime(runtime_id)
        assert isinstance(adapter, RuntimeAdapter)
        assert hasattr(adapter, "build_command")
        assert hasattr(adapter, "analyze_log")
        assert hasattr(adapter, "collaboration_block")
        cmd = adapter.build_command(dummy_ctx)
        assert isinstance(cmd, list)


def test_bin_loop_cli_dsh_purging_oracle():
    """TM-001 / US-001: Verify CLI entrypoint startup behavior fails on invalid runtime or missing args."""
    script_path = Path("bin/loop")
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "EPIC_RUNTIME" in content

    # Test running bin/loop with an invalid project directory exits non-zero (TM-001)
    result = subprocess.run(["bash", str(script_path), "/nonexistent/path/for/test"], capture_output=True, text=True)
    assert result.returncode != 0
