import pytest
from pathlib import Path
from harness.hooks import _lib
from loop.runtime_materializers.agent_policy import get_always_inject_set, parse_agent_policy


def test_always_inject_contains_verify_edit():
    """TM-005 / US-004: verify-edit in derived inject set."""
    inject_set = get_always_inject_set()
    assert "verify-edit" in inject_set


def test_sunset_inventory_injected_if_managed():
    """FR-008: sunset-inventory injected if managed."""
    inject_set = get_always_inject_set()
    assert "sunset-inventory" in inject_set


def test_software_verify_implement_gate_repair_still_injected():
    """AC+4: software+video+repair+sunset all present in inject set."""
    inject_set = get_always_inject_set()
    assert "verify-implement" in inject_set
    assert "gate-repair" in inject_set
    assert "verify-bugfix" in inject_set
    assert "verify-qa" in inject_set
    assert "verify-decompose" in inject_set
    assert "analyze-verify" in inject_set
    assert "reviewer" in inject_set
    assert "verify" in inject_set
    # video gates
    assert "verify-script" in inject_set
    assert "verify-publish" in inject_set


def test_derived_inject_set_not_software_only_literal():
    """AC-4: runtime SoT is derived from PolicyRecord.managed/verdict ∪ manifest/phase registry."""
    # subagent-start must use get_always_inject_set or derived set, not hardcoded software-only frozenset
    import importlib.util
    spec = importlib.util.spec_from_file_location("subagent_start", "harness/hooks/subagent-start.py")
    assert spec is not None and spec.loader is not None
    subagent_start_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subagent_start_mod)

    assert hasattr(subagent_start_mod, "get_always_inject_set") or hasattr(subagent_start_mod, "_ALWAYS_INJECT")
    active_inject = getattr(subagent_start_mod, "_ALWAYS_INJECT", None)
    if active_inject is None:
        active_inject = subagent_start_mod.get_always_inject_set()

    assert "verify-edit" in active_inject
    assert "sunset-inventory" in active_inject
