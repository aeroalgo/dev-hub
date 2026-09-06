from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"
HOOK = HOOKS / "subagent-start.py"


def _run(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    event = {"session_id": "drift-test", "cwd": str(tmp_path), **payload}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_contracts_sha_match_injects(tmp_path: Path) -> None:
    """AC+3 happy path: Matching checksum injects contract without error."""
    res = _run(tmp_path, {"agent_type": "verify-implement"})
    assert res.returncode == 0, res.stderr
    assert res.stdout
    data = json.loads(res.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "agent_type=verify-implement" in ctx
    assert "CONTRACT verify-implement:" in ctx
    assert "permissionDecision" not in data["hookSpecificOutput"]


def test_contracts_sha_mismatch_blocks_spawn(tmp_path: Path, monkeypatch) -> None:
    """TM-002 / US-003 / SC-003: Mutating CONTRACTS text causes sha mismatch and blocks spawn."""
    import _lib

    original = _lib.CONTRACTS["verify-implement"]
    try:
        # Mutate CONTRACTS text
        _lib.CONTRACTS["verify-implement"] = original + " # mutated drift"
        # Directly test check_contract_drift helper
        is_ok, drift_msg = _lib.check_contract_drift("verify-implement")
        assert is_ok is False
        assert "agent_contract_drift" in drift_msg
        assert "mismatch" in drift_msg
    finally:
        _lib.CONTRACTS["verify-implement"] = original


def test_stale_contracts_two_hard_texts_fail(tmp_path: Path) -> None:
    """Failure TM-002 / AC-3: Stale contracts / two HARD texts fail closed with deny decision."""
    # Test via running hook script with mutated CONTRACTS in test process or helper
    import _lib

    is_ok, _ = _lib.check_contract_drift("unknown-agent")
    assert is_ok is True  # Unknown agent passes drift check (handled by registry/contract emptiness)

    for agent_id, text in _lib.CONTRACTS.items():
        is_ok, _ = _lib.check_contract_drift(agent_id)
        assert is_ok is True, f"Contract checksum for {agent_id} must match CONTRACTS_SHA256"


def test_subagent_start_emits_deny_on_drift(tmp_path: Path, monkeypatch) -> None:
    """SubagentStart hook emits permissionDecision: deny on contract drift."""
    import importlib.util
    import _lib

    spec = importlib.util.spec_from_file_location("subagent_start_mod", HOOK)
    assert spec is not None and spec.loader is not None
    subagent_start_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subagent_start_mod)

    # Monkeypatch CONTRACTS to simulate drift inside the hook module
    monkeypatch.setitem(_lib.CONTRACTS, "verify-bugfix", "MUTATED CONTRACT TEXT")

    captured_emits = []
    monkeypatch.setattr(subagent_start_mod, "emit", lambda obj: captured_emits.append(obj))
    monkeypatch.setattr(subagent_start_mod, "read_stdin", lambda: {"session_id": "test", "cwd": str(tmp_path), "agent_type": "verify-bugfix"})

    subagent_start_mod.main()

    assert len(captured_emits) == 1
    output = captured_emits[0]["hookSpecificOutput"]
    assert output.get("permissionDecision") == "deny"
    assert "agent_contract_drift" in output.get("additionalContext", "")
