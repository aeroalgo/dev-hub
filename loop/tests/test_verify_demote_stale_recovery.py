"""After demote, fixed shard must remirror PASS; stale demote must not lie forever."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
sys.path.insert(0, str(HOOKS))

EPIC = "T-HUB-086-python-loop-supervisor-cutover"
STEP = "s04"
DECOMPOSE = f"memory-bank/back/plan/{EPIC}/yaml/decompose-index.yaml"
IMPLEMENT = f"memory-bank/back/implement/{EPIC}/s04-outer-orchestrator-and-lifecycle.yaml"


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _implement_body(*, checkpoints_done: bool, integration_ok: bool) -> str:
    cp_status = "done" if checkpoints_done else "pending"
    if integration_ok:
        integ = "- bin/pytest loop/tests/test_runner_orchestrator.py -q\n"
    else:
        integ = (
            "- command: bin/pytest loop/tests/test_runner_orchestrator.py -q\n"
            "  result: 7 passed\n"
        )
    return (
        "schema: epic-implement/v1\n"
        "role: back\n"
        f"step_id: {STEP}\n"
        f"plan_id: {EPIC}\n"
        "title: s04\n"
        "status: in_progress\n"
        "date: '2026-09-11'\n"
        "done:\n- orchestrator wired\n"
        "files:\n- loop/runner/orchestrator.py\n"
        "tests:\n- bin/pytest loop/tests/test_runner_orchestrator.py -q\n"
        "integration_check:\n"
        f"{integ}"
        "gaps:\n  status: none\n"
        "checkpoints:\n"
        f"- id: cp1\n  criterion: lifecycle\n  status: {cp_status}\n"
        f"- id: cp2\n  criterion: retry\n  status: {cp_status}\n"
        f"- id: cp3\n  criterion: decisions\n  status: {cp_status}\n"
    )


def _seed_epic(tmp_path: Path, session_id: str, *, demoted: bool) -> None:
    from epic.core import default_state, save_epic_state
    from touch_ledger import reset_touch_ledger

    _write(
        tmp_path,
        DECOMPOSE,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {EPIC}\n"
        "steps:\n"
        f"- id: {STEP}\n  file: s04-outer-orchestrator-and-lifecycle.yaml\n"
        "  next_phase: BACK IMPLEMENT\n  title: s04\n  status: pending\n",
    )
    reset_touch_ledger(tmp_path, epic_id=EPIC, step_id=STEP)
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "armed_epic": EPIC,
            "armed_decompose": DECOMPOSE,
            "armed_step": STEP,
            "armed_role": "BACK",
            "role": "BACK",
            "session_id": session_id,
            "phase_run_id": "run-s04",
            "projection_hash": "sha256:proj",
            "phase_epoch": "sha256:epoch",
            "event_digest": "sha256:event",
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK IMPLEMENT",
                "step_id": STEP,
                "epic_id": EPIC,
                "role": "BACK",
                "phase_run_id": "run-s04",
                "session_id": session_id,
            },
            "gate_identity": {
                "schema": "loop-gate-identity/v1",
                "session_id": session_id,
                "epic_id": EPIC,
                "step_id": STEP,
                "step": STEP,
                "role": "BACK",
                "phase": "BACK IMPLEMENT",
                "phase_run_id": "run-s04",
                "projection_hash": "sha256:proj",
                "phase_epoch": "sha256:epoch",
                "event_digest": "sha256:event",
                "authority": "autonomous",
            },
        }
    )
    if demoted:
        receipt = {
            "schema": "loop-verifier-receipt/v1",
            "session_id": session_id,
            "epic_id": EPIC,
            "role": "BACK",
            "step": STEP,
            "verifier_identity": "verify-implement",
            "verdict": "FAIL",
            "authority": "autonomous",
            "demoted_from_pass": True,
            "demote_blockers": [
                "implement_load_failed: integration_check.0 Input should be a valid string"
            ],
        }
        st["last_verify_verdict"] = "FAIL"
        st["last_verify_evidence"] = receipt
        st["last_verify_receipt"] = receipt
    save_epic_state(tmp_path, st)


def _mark_spawn(tmp_path: Path, session_id: str) -> None:
    from _lib import load_state, mark_in_flight, save_state

    st = load_state(session_id, str(tmp_path))
    mark_in_flight(
        st,
        agent="verify-implement",
        model="test-model",
        managed=True,
        cwd=str(tmp_path),
        session_id=session_id,
    )
    save_state(session_id, str(tmp_path), st)


def _run_stop(tmp_path: Path, *, message: str, session_id: str) -> subprocess.CompletedProcess[str]:
    stop = HOOKS / "subagent-stop.py"
    payload = {
        "agent_type": "verify-implement",
        "session_id": session_id,
        "runtime_id": "codex",
        "tool_use_id": "wait-recovery-1",
        "cwd": str(tmp_path),
        "last_assistant_message": message,
        "stop_hook_active": False,
    }
    env = os.environ.copy()
    env["EPIC_RUNTIME"] = "codex"
    env["EPIC_RUNTIME_RESOLVED"] = "codex"
    env["HUB_ROOT"] = str(tmp_path)
    env["DEV_HUB"] = str(tmp_path)
    env["PROJECT_ROOT"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
        env=env,
    )


def test_stale_demote_ready_after_shard_fix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    session_id = "sess-stale-demote-ready"
    _seed_epic(tmp_path, session_id, demoted=True)
    _write(tmp_path, IMPLEMENT, _implement_body(checkpoints_done=True, integration_ok=True))

    from epic.core import _verify_pass_ready_for_step

    ready = _verify_pass_ready_for_step(tmp_path, STEP)
    assert ready.get("ok") is False
    assert ready.get("diagnostic") == "verify_demoted_stale"
    assert "stale" in str(ready.get("error") or "").lower()
    assert "integration_check.0" not in str(ready.get("error") or "")


def test_demoted_then_fixed_shard_remirrors_autonomous_pass(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("EPIC_RUNNER_SESSION_ID", raising=False)

    session_id = "sess-demote-then-fix"
    _seed_epic(tmp_path, session_id, demoted=True)
    _write(tmp_path, IMPLEMENT, _implement_body(checkpoints_done=False, integration_ok=False))

    from epic.core import _verify_pass_ready_for_step, load_epic_state

    ready_blocked = _verify_pass_ready_for_step(tmp_path, STEP)
    assert ready_blocked.get("diagnostic") == "verify_demoted_pass"

    _write(tmp_path, IMPLEMENT, _implement_body(checkpoints_done=True, integration_ok=True))
    _mark_spawn(tmp_path, session_id)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": STEP,
        "epic_id": EPIC,
        "session_id": session_id,
        "recorded_at": "2026-09-11T00:00:00Z",
    }
    message = "```json\n" + json.dumps(fence) + "\n```\nVERDICT: PASS\n"
    proc = _run_stop(tmp_path, message=message, session_id=session_id)
    assert proc.returncode == 0, proc.stderr
    assert "PASS demoted → FAIL" not in proc.stderr

    after = load_epic_state(tmp_path)
    assert after.get("last_verify_verdict") == "PASS"
    receipt = after.get("last_verify_receipt") or {}
    assert receipt.get("demoted_from_pass") is not True
    assert receipt.get("authority") == "autonomous"


def test_mirror_rejects_manual_pass_for_implement_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    session_id = "sess-manual-poison"
    _seed_epic(tmp_path, session_id, demoted=False)
    _write(tmp_path, IMPLEMENT, _implement_body(checkpoints_done=True, integration_ok=True))

    from epic.core import load_epic_state, mirror_verify_verdict

    mirror_verify_verdict(
        tmp_path,
        "PASS",
        evidence={
            "schema": "loop-verifier-receipt/v1",
            "session_id": session_id,
            "epic_id": EPIC,
            "role": "BACK",
            "step": STEP,
            "verifier_identity": "verify-implement",
            "verdict": "PASS",
            "authority": "manual",
        },
        session_id=session_id,
        agent_id="verify-implement",
    )
    after = load_epic_state(tmp_path)
    assert after.get("last_verify_verdict") != "PASS"
    assert after.get("gate_diagnostic") == "manual_authority_rejected"
