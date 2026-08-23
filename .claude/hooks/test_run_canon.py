"""Shared test-runner timeout constants."""

TEST_TIMEOUT_SECONDS = 300
TEST_TIMEOUT_PREFIX = f"timeout {TEST_TIMEOUT_SECONDS}s "
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
ALLOWED_TEST_PREFIXES = TIMEOUT_TEST_PREFIXES


def has_external_timeout(command: str) -> bool:
    return command.startswith(TEST_TIMEOUT_PREFIX)
