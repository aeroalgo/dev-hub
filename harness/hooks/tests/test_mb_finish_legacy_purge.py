"""Test that all legacy FINISH blocks and dual activeContext write paths are purged."""

import subprocess
import pytest


def test_no_implement_finish_block_symbol():
    """rg _implement_finish_block loop/context_loop.py → 0 lines."""
    res = subprocess.run(
        "rg '_implement_finish_block' loop/context_loop.py",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, f"Found _implement_finish_block:\n{res.stdout}"


def test_no_qa_finish_block_symbol():
    """rg _qa_finish_block loop/context_loop.py → 0 lines."""
    res = subprocess.run(
        "rg '_qa_finish_block' loop/context_loop.py",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0, f"Found _qa_finish_block:\n{res.stdout}"


def test_sole_writer_audit():
    """No ad-hoc activeContext schema lines outside render_active_context, mb_finish, test, yaml."""
    cmd = (
        "rg 'schema: loop-handoff/v1' loop/ harness/ | "
        "grep -v 'render_active_context\\|mb_finish\\|test\\|#\\|.yaml' | wc -l"
    )
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    count = res.stdout.strip()
    assert count == "0", f"Found ad-hoc activeContext write paths:\n{res.stdout}"


def test_full_mb_finish_suite_green():
    """Regression check for mb_finish tests."""
    res = subprocess.run(
        ".venv/bin/pytest harness/hooks/tests/ -q --tb=line "
        "-k 'mb_finish and not test_full_mb_finish_suite_green'",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"mb_finish test suite failed:\n{res.stdout}"
