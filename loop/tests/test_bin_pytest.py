from pathlib import Path
import subprocess
import time


def test_bin_pytest_wrapper_exists_and_uses_timeout() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "bin" / "pytest"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "timeout -k 10s 300s" in text
    assert ".venv/bin/pytest" in text


def test_gnu_timeout_kill_after_escalates_past_ignored_term() -> None:
    started = time.monotonic()
    proc = subprocess.run(
        [
            "timeout",
            "-k",
            "1s",
            "1s",
            "bash",
            "-c",
            'trap "" TERM; sleep 60',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode != 0
    assert elapsed < 5.0, f"kill-after did not fire; elapsed={elapsed:.2f}s rc={proc.returncode}"
