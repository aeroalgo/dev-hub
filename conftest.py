from __future__ import annotations

import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    configured = os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS")
    if configured:
        try:
            return max(1, int(configured))
        except ValueError:
            pass
    return 4


@pytest.fixture(autouse=True)
def _isolate_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    env_before = os.environ.copy()
    for key in (
        "EPIC_RUNTIME",
        "EPIC_RUNTIME_RESOLVED",
        "EPIC_RUNNER_SESSION_ID",
        "EPIC_LOOP",
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "PROJECT_ROOT",
        "EPIC_PROJECT_ROOT",
        "DEV_HUB",
        "HUB_ROOT",
        "CLAUDE_PROJECT_DIR",
        "DSH_HOOKS_BRIDGE",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    os.environ.clear()
    os.environ.update(env_before)
