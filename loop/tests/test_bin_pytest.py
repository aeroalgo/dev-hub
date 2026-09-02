from pathlib import Path


def test_bin_pytest_wrapper_exists_and_uses_timeout() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "bin" / "pytest"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "timeout 300s" in text
    assert ".venv/bin/pytest" in text
