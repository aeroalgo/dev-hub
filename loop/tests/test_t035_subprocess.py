from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESILIENCE = ROOT / ".claude" / "hooks" / "session_resilience.py"
FIXTURE = ROOT / "loop" / "tests" / "fixtures" / "fake_claude.py"


def _run_wrapper(tmp_path: Path, mode: str, behavior: str, timeout: str = "2") -> tuple[int, str]:
    log = tmp_path / f"{mode}-{behavior}.log"
    proc = subprocess.run(
        [
            sys.executable,
            str(RESILIENCE),
            "run-session",
            "--mode",
            mode,
            "--session-id",
            f"s18-{mode}-{behavior}",
            "--timeout",
            timeout,
            "--kill-grace",
            "0.2",
            "--log",
            str(log),
            "--",
            sys.executable,
            str(FIXTURE),
            behavior,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, log.read_text(encoding="utf-8")


def test_subprocess_clean_path_preserves_stdout_stderr_and_success(tmp_path: Path) -> None:
    return_code, log = _run_wrapper(tmp_path, "headless", "clean")

    assert return_code == 0
    assert "stdout: clean" in log
    assert "stderr: clean" in log
    assert "SESSION_END" in log
    assert "SESSION_TIMEOUT" not in log


def test_subprocess_timeout_is_non_success_and_logs_bounded_abort(tmp_path: Path) -> None:
    return_code, log = _run_wrapper(tmp_path, "headless", "hang", "0.2")

    assert return_code == 124
    assert "stdout: hanging" in log
    assert "stderr: hanging" in log
    assert "SESSION_TIMEOUT" in log
    assert "SESSION_END" in log


def test_subprocess_invalid_mode_fails_closed(tmp_path: Path) -> None:
    log = tmp_path / "invalid.log"
    proc = subprocess.run(
        [
            sys.executable,
            str(RESILIENCE),
            "run-session",
            "--mode",
            "unknown",
            "--session-id",
            "s18-invalid",
            "--timeout",
            "1",
            "--kill-grace",
            "0.1",
            "--log",
            str(log),
            "--",
            sys.executable,
            str(FIXTURE),
            "clean",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr
    assert not log.exists()
