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
    for key in (
        "EPIC_RUNTIME",
        "EPIC_RUNTIME_RESOLVED",
        "EPIC_RUNNER_SESSION_ID",
        "EPIC_LOOP",
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
    ):
        monkeypatch.delenv(key, raising=False)
