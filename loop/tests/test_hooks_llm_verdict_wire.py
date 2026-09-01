"""Tests for extract_verdict: JSON fence machine SoT (+ optional sidecar)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import extract_verdict


def _fence(verdict: str = "PASS", agent: str = "verify") -> str:
    return (
        "summary\n"
        "```json\n"
        f'{{"schema":"loop-gate-verdict/v1","agent_id":"{agent}",'
        f'"verdict":"{verdict}","recorded_at":"2026-08-31T12:00:00Z"}}\n'
        "```\n"
    )


def test_extract_verdict_reads_json_fence_without_cwd():
    assert extract_verdict(_fence("PASS"), agent_id="verify") == "PASS"
    assert extract_verdict(_fence("FAIL"), agent_id="verify") == "FAIL"


def test_extract_verdict_plain_verdict_line_not_machine():
    assert extract_verdict("VERDICT: PASS", agent_id="verify") is None


def test_extract_verdict_reads_sidecar_when_no_fence(tmp_path: Path):
    fake_record = MagicMock()
    fake_record.verdict = "PASS"
    with patch("loop.gate_verdict_store.read_gate_verdict", return_value=fake_record):
        assert (
            extract_verdict("no fence", cwd=str(tmp_path), agent_id="verify") == "PASS"
        )


def test_extract_verdict_fence_wins_over_sidecar(tmp_path: Path):
    fake_record = MagicMock()
    fake_record.verdict = "FAIL"
    with patch("loop.gate_verdict_store.read_gate_verdict", return_value=fake_record):
        assert (
            extract_verdict(_fence("PASS"), cwd=str(tmp_path), agent_id="verify")
            == "PASS"
        )
