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
    assert "dsh" in ids
    assert "codex" in ids
    assert reg.get_runtime_adapter_module("claude") == "loop.runtime_adapters.claude"
    assert reg.get_runtime_adapter_module("dsh") == "loop.runtime_adapters.dsh"
    assert reg.get_runtime_adapter_module("codex") == "loop.runtime_adapters.codex"


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
    assert reg.has_capability("dsh", "stream_json") is True
    assert reg.has_capability("dsh", "non_existent_cap") is False
    assert reg.has_capability("claude", "raw_exec") is True

    with pytest.raises(CapabilityError):
        reg.has_capability("unknown_runtime", "stream_json")


def test_registry_malformed_yaml_raises(tmp_path: Path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("schema_version: invalid-v1\nruntimes: []")
    with pytest.raises(InvalidRuntimeConfig):
        load_registry(bad_yaml)

    corrupt_yaml = tmp_path / "corrupt.yaml"
    corrupt_yaml.write_text("::invalid yaml::")
    with pytest.raises(InvalidRuntimeConfig):
        load_registry(corrupt_yaml)
