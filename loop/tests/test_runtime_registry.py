import pytest
from pathlib import Path
from loop.runtime.registry import (
    load_registry,
    get_runtime_adapter,
    get_runtime_adapter_module,
    has_capability,
    list_ids,
    InvalidRuntimeConfig,
    CapabilityError,
)


def test_registry_load_valid_returns_both_runtimes():
    reg = load_registry()
    ids = reg.list_ids()
    assert "claude" in ids
    assert "codex" in ids
    assert "dsh" not in ids
    assert reg.get_runtime_adapter_module("claude") == "loop.runtime_adapters.claude"
    assert reg.get_runtime_adapter_module("codex") == "loop.runtime_adapters.codex"
    with pytest.raises(InvalidRuntimeConfig):
        reg.get_runtime_adapter_module("dsh")


def test_codex_entry_exists():
    reg = load_registry()
    assert "codex" in reg.list_ids()
    assert reg.get_runtime_adapter_module("codex") == "loop.runtime_adapters.codex"


def test_codex_adapter_instantiated():
    from loop.runtime_adapters.common import get_adapter_for_runtime
    from loop.runtime_adapters.codex import CodexAdapter

    adapter = get_adapter_for_runtime("codex")
    assert isinstance(adapter, CodexAdapter)


def test_codex_capabilities():
    reg = load_registry()
    assert reg.has_capability("codex", "headless") is True
    assert reg.has_capability("codex", "bridge_subagents") is True


def test_unknown_runtime_fail_closed():
    from loop.runtime_adapters.common import get_adapter_for_runtime

    with pytest.raises(ValueError, match="Unknown runtime: foo"):
        get_adapter_for_runtime("foo")


def test_foo_fail_closed():
    from loop.runtime_adapters.common import get_adapter_for_runtime

    with pytest.raises(ValueError):
        get_adapter_for_runtime("foo")


def test_registry_unknown_id_raises_invalid_runtime_config():
    reg = load_registry()
    with pytest.raises(InvalidRuntimeConfig):
        reg.get_runtime_adapter_module("unknown_id")

    with pytest.raises(InvalidRuntimeConfig):
        reg.get_runtime_adapter("unknown_id")

    with pytest.raises(InvalidRuntimeConfig):
        get_runtime_adapter_module("unknown_id")


def test_registry_capability_check_true_false():
    reg = load_registry()
    assert reg.has_capability("codex", "headless") is True
    assert reg.has_capability("codex", "non_existent_cap") is False
    assert reg.has_capability("claude", "raw_exec") is True

    with pytest.raises(CapabilityError):
        reg.has_capability("dsh", "stream_json")

    with pytest.raises(CapabilityError):
        reg.has_capability("unknown_runtime", "stream_json")


def test_registry_malformed_yaml_raises(tmp_path: Path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("schema_version: invalid-v1\nruntimes: []", encoding="utf-8")
    with pytest.raises(InvalidRuntimeConfig):
        load_registry(bad_yaml)

    corrupt_yaml = tmp_path / "corrupt.yaml"
    corrupt_yaml.write_text("::invalid yaml::", encoding="utf-8")
    with pytest.raises(InvalidRuntimeConfig):
        load_registry(corrupt_yaml)


def test_get_adapter_for_runtime_canonical_adapters():
    from loop.runtime_adapters.common import get_adapter_for_runtime
    from loop.runtime_adapters.claude import ClaudeAdapter
    from loop.runtime_adapters.codex import CodexAdapter

    assert isinstance(get_adapter_for_runtime("claude"), ClaudeAdapter)
    assert isinstance(get_adapter_for_runtime("claude-code"), ClaudeAdapter)
    assert isinstance(get_adapter_for_runtime("codex"), CodexAdapter)

    with pytest.raises(ValueError, match="Unknown runtime: dsh"):
        get_adapter_for_runtime("dsh")


def test_get_adapter_for_runtime_purged_aliases_fail_closed():
    from loop.runtime_adapters.common import get_adapter_for_runtime

    with pytest.raises(ValueError, match="Unknown runtime: claude_cli"):
        get_adapter_for_runtime("claude_cli")
    with pytest.raises(ValueError, match="Unknown runtime: claude-cli"):
        get_adapter_for_runtime("claude-cli")


def test_get_adapter_for_runtime_no_blind_dir_scan():
    import types
    from unittest.mock import patch
    from loop.runtime_adapters.common import get_adapter_for_runtime

    class RandomFallbackAdapter:
        pass

    mock_mod = types.ModuleType("mock_mod")
    mock_mod.RandomFallbackAdapter = RandomFallbackAdapter
    with patch("loop.runtime_adapters.common.get_runtime_adapter", return_value=mock_mod):
        with pytest.raises(ValueError, match="No RuntimeAdapter implementation found in adapter module for runtime 'claude'"):
            get_adapter_for_runtime("claude")
