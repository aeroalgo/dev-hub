from __future__ import annotations

import pytest
from unittest.mock import patch

from harness.hooks.tests_format import (
    validate_tests_entries,
    is_allowed_test_command,
    extract_test_commands_from_yaml_tests,
)
from harness.hooks.test_run_canon import ALLOWED_TEST_PREFIXES


def test_hub_test_format_validates_hub_commands() -> None:
    """Hub test validation accepts hub test runner prefixes."""
    tests = [
        "`bin/pytest loop/tests/test_foo.py -q`",
        "`cd frontend && npm exec vitest`",
    ]
    errors = validate_tests_entries(tests, finish=True, require_executable=True)
    assert not errors

    extracted = extract_test_commands_from_yaml_tests(tests)
    assert "bin/pytest loop/tests/test_foo.py -q" in extracted
    assert is_allowed_test_command("bin/pytest loop/tests/test_foo.py -q")


def test_generic_command_canon_is_not_managed_target_authority() -> None:
    """ALLOWED_TEST_PREFIXES and is_allowed_test_command are hub-only test format canon, not managed targets."""
    # Managed target commands like `cargo test` or arbitrary `pytest` without hub prefix are not allowed in raw hub tests
    assert not is_allowed_test_command("cargo test --all-targets")
    assert not is_allowed_test_command("npm run test")
    assert not any(p.startswith("cargo") for p in ALLOWED_TEST_PREFIXES)
