"""Coerce demote must not be undone by empty-ledger scope promote."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness" / "hooks"))


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run_stop(
    tmp_path: Path,
    *,
    message: str,
    session_id: str,
    runtime_id: str = "codex",
) -> subprocess.CompletedProcess[str]:
    stop = ROOT / "harness" / "hooks" / "subagent-stop.py"
    payload = {
        "agent_type": "verify-implement",
        "session_id": session_id,
        "runtime_id": runtime_id,
        "tool_use_id": "wait-demote-1",
        "cwd": str(tmp_path),
        "last_assistant_message": message,
        "stop_hook_active": False,
    }
    env = os.environ.copy()
    env["EPIC_RUNTIME"] = runtime_id
    env["EPIC_RUNTIME_RESOLVED"] = runtime_id
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


def test_demoted_pass_not_promoted_by_transport_bind_report(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("EPIC_RUNNER_SESSION_ID", raising=False)

    from epic.core import default_state, load_epic_state, save_epic_state
    from touch_ledger import reset_touch_ledger

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-demote-no-promote"
    decompose = f"memory-bank/back/plan/{epic}/yaml/decompose-index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s05\n  file: s05-codex-stop-transport-bind-and-coerce-removal.yaml\n"
        "  next_phase: BACK IMPLEMENT\n  title: s05\n  status: pending\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/implement/{epic}/s05-codex-stop-transport-bind-and-coerce-removal.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s05\n"
        f"plan_id: {epic}\n"
        "title: s05\nstatus: in_progress\ndate: '2026-09-10'\n"
        "done: []\nfiles: []\ntests: []\nintegration_check: []\n"
        "gaps:\n  status: blocked\n  items: [incomplete]\n"
        "checkpoints:\n"
        "- id: cp1\n  criterion: transport bind\n  status: pending\n",
    )
    reset_touch_ledger(tmp_path, epic_id=epic, step_id="s05")

    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "s05",
            "armed_role": "BACK",
            "role": "BACK",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK IMPLEMENT",
                "step_id": "s05",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": "s05",
        "epic_id": epic,
        "session_id": session_id,
        "recorded_at": "2026-09-10T00:00:00Z",
    }
    message = (
        "```json\n"
        + json.dumps(fence)
        + "\n```\n"
        "AC+: A3 PASS — bind_fence(policy=\"transport_bind\").\n"
        "AC−: N3 PASS — scope-check ok, oos_ledger_paths=[].\n"
        "VERIFY: PASS — 5 passed.\n"
        "BLOCKERS: нет.\n"
    )
    proc = _run_stop(tmp_path, message=message, session_id=session_id)
    assert proc.returncode == 0, proc.stderr
    assert "PASS demoted → FAIL" in proc.stderr
    assert "promoted → PASS" not in proc.stderr
    assert "automatic mb-finish completed" not in proc.stderr
    assert "VERDICT: PASS — parent" not in proc.stderr
    assert "mb-finish implement" not in proc.stderr or "FORBIDDEN: mb-finish" in proc.stderr

    after = load_epic_state(tmp_path)
    assert after.get("last_verify_verdict") == "FAIL"
    receipt = after.get("last_verify_receipt") or {}
    assert receipt.get("demoted_from_pass") is True
    assert after.get("gate_diagnostic") != "verify_spawn_missing"

    from epic.core import _verify_pass_ready_for_step

    ready = _verify_pass_ready_for_step(tmp_path, "s05")
    assert ready.get("ok") is False
    assert ready.get("diagnostic") == "verify_demoted_pass"
    assert "demoted" in str(ready.get("error") or "").lower()


def test_stale_demoted_receipt_does_not_emit_pass_mb_finish_hint(
    tmp_path: Path, monkeypatch
) -> None:
    """Re-verify PASS while SoT still holds demoted FAIL must not nudge mb-finish."""
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("EPIC_RUNNER_SESSION_ID", raising=False)

    from epic.core import default_state, load_epic_state, save_epic_state
    from touch_ledger import reset_touch_ledger

    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-stale-demote-no-hint"
    decompose = f"memory-bank/back/plan/{epic}/yaml/decompose-index.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "steps:\n"
        "- id: s05\n  file: s05-codex-stop-transport-bind-and-coerce-removal.yaml\n"
        "  next_phase: BACK IMPLEMENT\n  title: s05\n  status: pending\n",
    )
    _write(
        tmp_path,
        f"memory-bank/back/implement/{epic}/s05-codex-stop-transport-bind-and-coerce-removal.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s05\n"
        f"plan_id: {epic}\n"
        "title: s05\nstatus: in_progress\ndate: '2026-09-10'\n"
        "done: []\nfiles: []\ntests: []\nintegration_check: []\n"
        "gaps:\n  status: blocked\n  items: [incomplete]\n"
        "checkpoints:\n"
        "- id: cp1\n  criterion: transport bind\n  status: pending\n",
    )
    reset_touch_ledger(tmp_path, epic_id=epic, step_id="s05")

    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "armed_epic": epic,
            "armed_decompose": decompose,
            "armed_step": "s05",
            "armed_role": "BACK",
            "role": "BACK",
            "session_id": session_id,
            "last_verify_verdict": "FAIL",
            "last_verify_evidence": {
                "schema": "loop-verifier-receipt/v1",
                "session_id": session_id,
                "epic_id": epic,
                "role": "BACK",
                "step": "s05",
                "verdict": "PASS",
                "demoted_from_pass": True,
                "demote_blockers": ["checkpoints not done: cp1"],
                "authority": "autonomous",
            },
            "last_verify_receipt": {
                "schema": "loop-verifier-receipt/v1",
                "session_id": session_id,
                "epic_id": epic,
                "role": "BACK",
                "step": "s05",
                "verdict": "PASS",
                "demoted_from_pass": True,
                "demote_blockers": ["checkpoints not done: cp1"],
                "authority": "autonomous",
            },
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK IMPLEMENT",
                "step_id": "s05",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-1",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    fence = {
        "schema": "loop-gate-verdict/v1",
        "agent_id": "verify-implement",
        "verdict": "PASS",
        "step_id": "s05",
        "epic_id": epic,
        "session_id": session_id,
        "recorded_at": "2026-09-10T00:00:00Z",
    }
    message = "```json\n" + json.dumps(fence) + "\n```\nVERDICT: PASS\n"
    proc = _run_stop(tmp_path, message=message, session_id=session_id)
    assert proc.returncode == 0, proc.stderr
    assert "VERDICT: PASS — parent" not in proc.stderr
    assert "automatic mb-finish completed" not in proc.stderr
    after = load_epic_state(tmp_path)
    assert after.get("last_verify_verdict") == "FAIL"
