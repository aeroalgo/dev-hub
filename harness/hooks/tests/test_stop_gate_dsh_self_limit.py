from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STOP_GATE = ROOT / "harness" / "hooks" / "stop-gate.py"


def test_stopgate_no_is_dsh_runtime_function() -> None:
    text = STOP_GATE.read_text(encoding="utf-8")
    assert "_is_dsh_runtime" not in text
    assert "_dsh_self_limit" not in text
    assert "DSH self-limit" not in text
