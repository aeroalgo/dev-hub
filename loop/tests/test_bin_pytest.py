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


def test_bin_pytest_wrapper_defaults_to_parallel_xdist() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "bin" / "pytest"
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert "timeout -k 10s 300s" in text
    assert ".venv/bin/pytest" in text
    assert "pytest-xdist" in text
    assert "--dist" in text
    assert "PYTEST_WORKERS" in text
    assert "default_workers=4" in text


def test_parallel_pytest_wrapper_delegates_to_canonical_runner() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "bin" / "pytest-parallel"
    text = script.read_text(encoding="utf-8")
    assert script.is_file()
    assert 'exec "$ROOT/bin/pytest" "$@"' in text


def test_pytest_config_enables_parallel_defaults() -> None:
    root = Path(__file__).resolve().parents[2]
    config = (root / "pytest.ini").read_text(encoding="utf-8")
    assert "addopts = -n 4 --dist loadfile" in config


def test_pytest_auto_worker_hook_defaults_to_four_cpus() -> None:
    root = Path(__file__).resolve().parents[2]
    hook = (root / "conftest.py").read_text(encoding="utf-8")
    assert "pytest_xdist_auto_num_workers" in hook
    assert "return 4" in hook
    assert "PYTEST_XDIST_AUTO_NUM_WORKERS" in hook


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
