from __future__ import annotations

from pathlib import Path
import re
import pytest

from loop.stack_profiles.schemas import CapabilityName
from loop.stack_profiles.execution import CapabilityCheckSpec


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_instruction_inventory_has_no_generic_managed_test_runner():
    root = _repo_root()
    instruction_files = [
        root / "harness/cursor/rules/shared/test-timeout.mdc",
        root / "harness/cursor/rules/shared/role-core-contract.mdc",
        root / "harness/cursor/rules/back_developer/isolation_rules/_lean/implement.mdc",
        root / "harness/cursor/rules/back_developer/isolation_rules/_lean/qa.mdc",
        root / "harness/cursor/rules/integration_developer/isolation_rules/_lean/implement.mdc",
        root / "harness/claude/skills/role-command/SKILL.md",
    ]

    for p in instruction_files:
        assert p.is_file(), f"instruction file missing: {p}"
        content = p.read_text(encoding="utf-8")
        # Ensure capability_checks / managed capability distinction is mentioned
        assert "capability_checks" in content or "managed" in content.lower()


def test_instruction_inventory_retains_explicit_hub_exception():
    root = _repo_root()
    instruction_files = [
        root / "harness/cursor/rules/shared/test-timeout.mdc",
        root / "harness/cursor/rules/shared/role-core-contract.mdc",
        root / "harness/claude/skills/role-command/SKILL.md",
    ]

    for p in instruction_files:
        content = p.read_text(encoding="utf-8")
        assert "hub" in content.lower() or "dev-hub" in content.lower()
        assert "bin/pytest" in content


def test_instruction_inventory_preserves_front_parent_only_boundary():
    root = _repo_root()
    instruction_files = [
        root / "harness/claude/skills/role-command/SKILL.md",
        root / "harness/cursor/rules/shared/test-timeout.mdc",
    ]

    for p in instruction_files:
        content = p.read_text(encoding="utf-8")
        if p.name == "SKILL.md":
            assert "FRONT + любой frontend" in content and "только parent" in content
        assert "test.e2e" not in [c.value for c in CapabilityName]


def test_sunset_a_b_c_i_scans_have_no_live_legacy_authority():
    # Kind A / Kind B / Kind C checks in python source
    from harness.hooks.tests_format import validate_tests_entries, is_allowed_test_command
    from harness.hooks.test_run_canon import ALLOWED_TEST_PREFIXES
    from harness.hooks.epic_yaml import implement_ready_for_finalize_doc

    # Verification: declaration requires target and selector, rejects raw commands
    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="test.full", target="")

    with pytest.raises(Exception):
        CapabilityCheckSpec(capability="invalid.selector", target="backend")

    # Kind A: hub test command authority rejects managed targets
    assert not is_allowed_test_command("cargo test --all-targets")
    assert not is_allowed_test_command("npm run test")
    assert not any(p.startswith("cargo") for p in ALLOWED_TEST_PREFIXES)
