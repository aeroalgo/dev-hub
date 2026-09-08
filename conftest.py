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

    try:
        cpu_count = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpu_count = os.cpu_count() or 1
    return max(1, cpu_count - 2)
