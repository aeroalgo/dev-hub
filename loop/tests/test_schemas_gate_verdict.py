"""Tests for loop/schemas/gate_verdict.py and loop/gate_verdict_store.py."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
LOOP = ROOT / "loop"
for p in (str(HOOKS), str(LOOP)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _lib import extract_verdict
from loop.gate_verdict_store import (
    gate_verdict_for_step,
    gate_verdict_path,
    read_gate_verdict,
    write_gate_verdict,
)
from loop.schemas.gate_verdict import GateVerdictRecord


def test_write_invalid_verdict_raises_before_file_write(tmp_path: Path) -> None:
    agent_id = "test_agent"
    target_path = gate_verdict_path(tmp_path, agent_id)
    assert not target_path.exists()

    with pytest.raises(ValidationError):
        write_gate_verdict(
            tmp_path,
            agent_id,
            "INVALID_VERDICT",
            recorded_at="2026-08-31T12:00:00Z",
        )

    assert not target_path.exists()


def test_sidecar_pass_overrides_transcript_fail(tmp_path: Path) -> None:
    agent_id = "verify"
    write_gate_verdict(
        tmp_path,
        agent_id,
        "PASS",
        step_id="s01",
        session_id="sess_test",
        epic_id="T-HUB-001",
        recorded_at="2026-08-31T12:00:00Z",
    )

    transcript_text = "VERDICT: FAIL"
    res = extract_verdict(transcript_text, cwd=str(tmp_path), agent_id=agent_id)
    assert res == "PASS"


def test_verdict_record_round_trip(tmp_path: Path) -> None:
    agent_id = "verify_123"
    rec = write_gate_verdict(
        tmp_path,
        agent_id,
        "PASS",
        step_id="s08",
        session_id="sess_abc",
        epic_id="T-HUB-022",
        recorded_at="2026-08-31T12:00:00Z",
        evidence_sha256="abc123sha",
    )

    read_rec = read_gate_verdict(tmp_path, agent_id)
    assert read_rec is not None
    assert read_rec.agent_id == agent_id
    assert read_rec.verdict == "PASS"
    assert read_rec.step_id == "s08"
    assert read_rec.session_id == "sess_abc"
    assert read_rec.epic_id == "T-HUB-022"
    assert read_rec.recorded_at == "2026-08-31T12:00:00Z"
    assert read_rec.evidence_sha256 == "abc123sha"

    step_rec = gate_verdict_for_step(
        tmp_path, agent_id, step_id="s08", session_id="sess_abc"
    )
    assert step_rec is not None
    assert step_rec.verdict == "PASS"

    mismatch_step = gate_verdict_for_step(tmp_path, agent_id, step_id="s09")
    assert mismatch_step is None
