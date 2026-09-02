"""Test command format helpers for implement/refactor yaml `tests:` field."""
from __future__ import annotations

import re
from typing import Any

from test_run_canon import ALLOWED_TEST_PREFIXES, TIMEOUT_TEST_PREFIXES

_PYTEST_PREFIX = TIMEOUT_TEST_PREFIXES[0]
_ALLOWED_TEST_PREFIXES = ALLOWED_TEST_PREFIXES


def _strip_result_trailer(cmd: str) -> str:
    m = re.search(r"[—–]", cmd)
    if not m:
        return cmd
    left = cmd[: m.start()].rstrip()
    if any(left.startswith(p) for p in _ALLOWED_TEST_PREFIXES):
        return left
    return cmd


def normalize_test_command_entry(entry: str) -> str:
    cmd = entry.strip()
    if cmd.startswith("- "):
        cmd = cmd[2:].strip()
    if cmd.startswith("`") and cmd.endswith("`"):
        cmd = cmd[1:-1].strip()
    else:
        m = re.search(r"`([^`]+)`", cmd)
        if m:
            cmd = m.group(1).strip()
        else:
            cmd = _strip_result_trailer(cmd)
            cmd = re.sub(
                r"\s+(?:PASS|passed|FAIL|failed)\s*$",
                "",
                cmd,
                flags=re.IGNORECASE,
            ).rstrip()
    return _strip_result_trailer(cmd)


def is_allowed_test_command(cmd: str) -> bool:
    cmd = normalize_test_command_entry(cmd)
    return any(cmd.startswith(prefix) for prefix in _ALLOWED_TEST_PREFIXES)


def tests_entry_is_dirty_command_prose(entry: str) -> bool:
    s = entry.strip()
    if not s or "`" in s:
        return False
    if not any(s.startswith(p) for p in _ALLOWED_TEST_PREFIXES):
        return False
    if re.search(r"[—–]", s):
        return True
    return bool(re.search(r"\s+(?:PASS|passed|FAIL|failed)\s*$", s, re.IGNORECASE))


def _add_test_cmd(cmd: str, seen: set[str], out: list[str]) -> None:
    cmd = normalize_test_command_entry(cmd)
    if not is_allowed_test_command(cmd) or cmd in seen:
        return
    seen.add(cmd)
    out.append(cmd)


def extract_test_commands_from_yaml_tests(tests: list[str]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for raw in tests:
        if isinstance(raw, str):
            _add_test_cmd(raw, seen, commands)
    return commands[:5]


def validate_tests_entries(
    tests: list[Any] | None,
    *,
    finish: bool = True,
    require_executable: bool = True,
) -> list[str]:
    errors: list[str] = []
    if tests is None:
        tests = []
    if not isinstance(tests, list):
        return ["tests: must be a list of strings"]
    if finish and require_executable and not tests:
        return ["tests: at least one entry required on FINISH"]

    for i, raw in enumerate(tests):
        if isinstance(raw, dict):
            errors.append(
                f"tests[{i}]: FORBIDDEN mapping {{command:/result:}}; "
                "use string with cmd in `backticks`; result → verification_results"
            )
            continue
        if not isinstance(raw, str):
            errors.append(f"tests[{i}]: must be string, got {type(raw).__name__}")
            continue
        if tests_entry_is_dirty_command_prose(raw):
            errors.append(
                f"tests[{i}]: FORBIDDEN command+result prose in one string "
                f"({raw!r}); wrap command in `backticks`, "
                "put PASS/counts in verification_results"
            )

    if finish and require_executable:
        str_tests = [t for t in tests if isinstance(t, str)]
        cmds = extract_test_commands_from_yaml_tests(str_tests)
        if not cmds:
            errors.append(
                "tests: need ≥1 executable command with timeout 300s "
                "(bin/pytest … | "
                "timeout 300s .venv/bin/pytest … | "
                "timeout 300s npm exec vitest … | "
                "timeout 300s npm exec tsc …); wrap cmd in `backticks`"
            )
    return errors
