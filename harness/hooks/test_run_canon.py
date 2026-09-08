"""Shared test-runner timeout constants for dev-hub self tests (hub exception)."""

import shlex

TEST_TIMEOUT_SECONDS = 300
TEST_TIMEOUT_PREFIX = f"timeout {TEST_TIMEOUT_SECONDS}s "
BIN_PYTEST_PREFIX = "bin/pytest "
PYTEST_PREFIX = ".venv/bin/pytest "
BASE_TEST_PREFIXES = (
    PYTEST_PREFIX,
    "npm --prefix frontend exec vitest",
    "npm --prefix frontend exec tsc",
    "cd frontend && npm exec vitest",
    "cd frontend && npm exec tsc",
    "npm exec vitest",
    "npm exec tsc",
)
TIMEOUT_TEST_PREFIXES = tuple(
    TEST_TIMEOUT_PREFIX + prefix for prefix in BASE_TEST_PREFIXES
)
ALLOWED_TEST_PREFIXES = (BIN_PYTEST_PREFIX,) + TIMEOUT_TEST_PREFIXES


def has_external_timeout(command: str) -> bool:
    return command.startswith(TEST_TIMEOUT_PREFIX)


def is_full_hub_pytest_command(command: str) -> bool:
    """Return whether a pytest command collects the default repository suite."""
    try:
        tokens = shlex.split(command.strip().strip("`"))
    except ValueError:
        return False

    for index, token in enumerate(tokens):
        if token not in {"bin/pytest", ".venv/bin/pytest"}:
            continue
        args = tokens[index + 1 :]
        if any(arg == "-k" or arg.startswith("-k") for arg in args):
            return False
        return not any(not arg.startswith("-") for arg in args)
    return False
