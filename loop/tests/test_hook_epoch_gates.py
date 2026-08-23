from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_lib():
    sys.path.insert(0, str(HOOKS))
    import _lib

    return _lib


def test_identity_and_evidence_match_exact_projection() -> None:
    lib = _load_lib()
    identity = {
        "session_id": "session-1",
        "epic_id": "T-035",
        "role": "BACK",
        "step": "s12",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    evidence = lib.verdict_evidence(identity, "PASS")
    assert lib.match_gate_evidence(evidence, identity) == (True, "matched")


def test_session_id_mismatch_still_matches_same_projection() -> None:
    """Claude retries / aborted sessions change invoke id; projection binds PASS."""
    lib = _load_lib()
    current = {
        "session_id": "runner-stable",
        "epic_id": "T-046",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    evidence = lib.verdict_evidence(
        {**current, "session_id": "claude-retry-invoke"},
        "PASS",
    )
    assert lib.match_gate_evidence(evidence, current) == (True, "matched")


def test_missing_current_session_still_matches_projection() -> None:
    lib = _load_lib()
    current = {
        "session_id": None,
        "epic_id": "T-046",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    evidence = lib.verdict_evidence(
        {**current, "session_id": "claude-9f2519"},
        "PASS",
    )
    assert lib.match_gate_evidence(evidence, current) == (True, "matched")


def test_stale_epoch_or_hash_cannot_satisfy_gate() -> None:
    lib = _load_lib()
    identity = {
        "session_id": "session-1",
        "step": "s12",
        "projection_hash": "hash-2",
        "phase_epoch": "epoch-2",
    }
    evidence = lib.verdict_evidence(
        {
            **identity,
            "projection_hash": "hash-1",
            "phase_epoch": "epoch-1",
            "authority": "autonomous",
        },
        "PASS",
    )
    assert lib.match_gate_evidence(evidence, identity) == (False, "verdict_stale")


def test_record_verdict_rejects_stale_and_keeps_diagnostic() -> None:
    lib = _load_lib()
    state = {"gate_identity": {"session_id": "s", "step": "s12", "projection_hash": "h2", "phase_epoch": "e2"}}
    evidence = lib.verdict_evidence(
        {"session_id": "s", "step": "s12", "projection_hash": "h1", "phase_epoch": "e1", "authority": "autonomous"},
        "PASS",
    )
    matched, diagnostic = lib.record_verdict(state, "verify", "PASS", evidence)
    assert (matched, diagnostic) == (False, "verdict_stale")
    assert state["verify_done"] is False
    assert state["verify_verdict"] is None
    assert state["verify_evidence"]["diagnostic"] == "verdict_stale"


def test_manual_evidence_is_labeled_non_authoritative() -> None:
    lib = _load_lib()
    state = {"gate_identity": {"session_id": "s", "step": "s12", "projection_hash": "h", "phase_epoch": "e"}}
    evidence = lib.verdict_evidence({"authority": "manual"}, "PASS")
    matched, diagnostic = lib.record_verdict(state, "verify", "PASS", evidence)
    assert (matched, diagnostic) == (True, "manual_fallback_non_authoritative")
    assert state["verify_verdict"] == "PASS"
    assert state["verify_evidence"]["diagnostic"] == "manual_fallback_non_authoritative"


def test_verdict_dedupe_key_allows_fail_then_pass_retry() -> None:
    lib = _load_lib()
    fail_key = lib.verdict_dedupe_key("sess", "verify", verdict="FAIL")
    pass_key = lib.verdict_dedupe_key("sess", "verify", verdict="PASS")
    assert fail_key != pass_key
    tool_a = lib.verdict_dedupe_key("sess", "verify", tool_use_id="call_1", verdict="FAIL")
    tool_b = lib.verdict_dedupe_key("sess", "verify", tool_use_id="call_2", verdict="PASS")
    assert tool_a != tool_b
    state: dict = {"verdict_recorded_agents": [fail_key]}
    assert lib.should_skip_verdict_record(state, fail_key) is True
    assert lib.should_skip_verdict_record(state, pass_key) is False
    lib.mark_verdict_recorded(state, pass_key)
    assert pass_key in state["verdict_recorded_agents"]


def test_current_gate_identity_prefers_runner_session_over_claude(
    tmp_path: Path, monkeypatch
) -> None:
    lib = _load_lib()
    runner_session = "runner-9d1d186b"
    claude_session = "claude-568fce55"
    state = {
        "session_id": runner_session,
        "armed_epic": "T-045",
        "armed_step": "s03",
        "role": "BACK",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "projection": {
            "epic_id": "T-045",
            "role": "BACK",
            "next_step": "s03",
            "projection_hash": "hash-1",
            "phase_epoch": "epoch-1",
            "event_digest": "digest-1",
        },
    }
    state_path = tmp_path / ".claude" / "runtime" / "epic" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    identity = lib.current_gate_identity(str(tmp_path), claude_session)
    assert identity["session_id"] == runner_session
    evidence = lib.verdict_evidence(identity, "PASS")
    assert lib.match_gate_evidence(
        evidence,
        lib.gate_identity(state, runner_session),
    ) == (True, "matched")


def test_current_gate_identity_prefers_env_runner_over_claude(
    tmp_path: Path, monkeypatch
) -> None:
    lib = _load_lib()
    runner_session = "runner-from-env"
    claude_session = "claude-568fce55"
    state = {
        "session_id": None,
        "armed_epic": "T-046",
        "armed_step": "s01",
        "role": "BACK",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "projection": {
            "epic_id": "T-046",
            "role": "BACK",
            "next_step": "s01",
            "projection_hash": "hash-1",
            "phase_epoch": "epoch-1",
            "event_digest": "digest-1",
        },
    }
    state_path = tmp_path / ".claude" / "runtime" / "epic" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EPIC_RUNNER_SESSION_ID", runner_session)

    identity = lib.current_gate_identity(str(tmp_path), claude_session)
    assert identity["session_id"] == runner_session
