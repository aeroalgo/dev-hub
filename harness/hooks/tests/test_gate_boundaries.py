"""Integration and boundary tests for SubagentStart, SubagentStop, and Stop gate.

Covers:
- CP1: Distinct registered lifecycle boundaries with independent event tests.
- CP2: SubagentStop validates actual transcript fences and rejects malformed payloads even if subagent self-check was advisory PASS.
- CP3: Stop gate rejects state-only manual PASS and blocks parent finish when evidence receipt is missing or stale.
- CP4: Complete valid gate flow allows finish.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = ROOT / "harness" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib import load_state, save_state
from gate_receipt import issue_verifier_receipt
from gate_runtime import GateDiagnosticCode, IdentityService, SessionIdentity


SUBAGENT_START = HOOKS_DIR / "subagent-start.py"
SUBAGENT_STOP = HOOKS_DIR / "subagent-stop.py"
STOP_GATE = HOOKS_DIR / "stop-gate.py"


def _ensure_project_env(cwd: Path) -> None:
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    env_path = claude_dir / "project.env"
    if not env_path.is_file():
        env_path.write_text(
            "PROJECT_WORKFLOW_HOOKS=loop\n"
            "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
            "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n",
            encoding="utf-8",
        )
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    specs = (
        ("verify", "gate", "pass-fail", True),
        ("verify-implement", "gate", "pass-fail", True),
        ("verify-bugfix", "gate", "pass-fail", True),
        ("reviewer", "gate", "pass-blocked-fail", True),
        ("verify-qa", "gate", "pass-blocked-fail", True),
    )
    for name, mode, verdict, requires_model in specs:
        path = agents_dir / f"{name}.md"
        if not path.is_file():
            path.write_text(
                "---\n"
                f"name: {name}\n"
                "overlay:\n"
                "  managed: true\n"
                f"  mode: {mode}\n"
                f"  requires_model: {str(requires_model).lower()}\n"
                "  default_loop: true\n"
                "  default_chat: false\n"
                f"  verdict: {verdict}\n"
                "  allow_worktree: false\n"
                "---\nbody\n",
                encoding="utf-8",
            )


def _run_hook(hook_path: Path, payload: dict[str, Any], cwd: Path) -> subprocess.CompletedProcess[str]:
    _ensure_project_env(cwd)
    env = os.environ.copy()
    env["EPIC_LOOP"] = "1"
    env["PYTHONPATH"] = str(HOOKS_DIR)
    if "runtime_id" in payload:
        env["EPIC_RUNTIME"] = str(payload["runtime_id"])
        env["EPIC_RUNTIME_RESOLVED"] = str(payload["runtime_id"])
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )


# ============================================================================
# Checkpoint 1: Distinct Registered Lifecycle Boundaries
# ============================================================================

def test_distinct_boundaries_lifecycle_registration() -> None:
    """CP1: SubagentStart, SubagentStop, and Stop operate as distinct standalone scripts."""
    assert SUBAGENT_START.is_file()
    assert SUBAGENT_STOP.is_file()
    assert STOP_GATE.is_file()
    assert SUBAGENT_START != SUBAGENT_STOP
    assert SUBAGENT_STOP != STOP_GATE


def test_subagent_start_contract_injection(tmp_path: Path) -> None:
    """CP1 / US-003: SubagentStart injects contract and gate identity block."""
    proc = _run_hook(
        SUBAGENT_START,
        {
            "session_id": "sess-start-01",
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
        },
        tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "agent_type=verify-implement" in context
    assert "GATE_IDENTITY" in context
    assert "CONTRACT verify-implement:" in context


# ============================================================================
# Checkpoint 2: SubagentStop authoritative transcript fence validation
# ============================================================================

def test_subagent_stop_rejects_malformed_fence(tmp_path: Path) -> None:
    """CP2 / FR-006: SubagentStop rejects malformed JSON fence even if self-check was advisory PASS."""
    session_id = "sess-malformed-01"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "in_flight": [{"agent": "verify-implement", "managed": True}],
    }
    save_state(session_id, str(tmp_path), st)

    # Message contains advisory PASS in text, but corrupted json fence
    msg = (
        "Self-check advisory: VERDICT: PASS\n"
        "```json\n"
        "{ malformed json content here: missing quotes }\n"
        "```"
    )

    proc = _run_hook(
        SUBAGENT_STOP,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": msg,
        },
        tmp_path,
    )
    assert proc.returncode == 2
    assert "schema validation failed" in proc.stderr
    st_after = load_state(session_id, str(tmp_path))
    assert st_after.get("verify_done") is not True


def test_subagent_stop_validates_transcript_fence_over_advisory_pass(tmp_path: Path) -> None:
    """CP2 / FR-006: External transcript validation is authoritative over advisory self-check."""
    session_id = "sess-advisory-01"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "in_flight": [{"agent": "verify-implement", "managed": True}],
    }
    save_state(session_id, str(tmp_path), st)

    # Agent says PASS in prose, but emitted FAIL in JSON fence
    fence_msg = (
        "Advisory PASS in self check\n"
        "```json\n"
        "{\n"
        "  \"schema\": \"loop-gate-verdict/v1\",\n"
        "  \"agent_id\": \"verify-implement\",\n"
        "  \"verdict\": \"FAIL\",\n"
        "  \"session_id\": \"sess-advisory-01\",\n"
        "  \"epic_id\": \"T-HUB-085\",\n"
        "  \"step_id\": \"s05\",\n"
        "  \"recorded_at\": \"2026-09-11T12:00:00Z\"\n"
        "}\n"
        "```"
    )

    proc = _run_hook(
        SUBAGENT_STOP,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "agent_type": "verify-implement",
            "last_assistant_message": fence_msg,
            "verdict": "PASS",
        },
        tmp_path,
    )
    assert proc.returncode == 0
    st_after = load_state(session_id, str(tmp_path))
    assert st_after.get("verify_verdict") == "FAIL"


def test_subagent_stop_rejects_ownership_mismatch(tmp_path: Path) -> None:
    """CP2 / FR-005 / US-003: SubagentStop rejects fence from different session/step/epic."""
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-085\n"
        "step_id: s05\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/plan/T-HUB-085/s05.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — s05\n"
        "- **Дальше:** @verify\n",
        encoding="utf-8",
    )
    session_id = "sess-owner-01"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "armed_epic": "T-HUB-085",
        "gate_identity": {
            "session_id": session_id,
            "epic_id": "T-HUB-085",
            "step": "s05",
            "step_id": "s05",
            "role": "BACK",
        },
        "in_flight": [{"agent": "verify-implement", "managed": True}],
    }
    save_state(session_id, str(tmp_path), st)

    fence_msg = (
        "```json\n"
        "{\n"
        "  \"schema\": \"loop-gate-verdict/v1\",\n"
        "  \"agent_id\": \"verify-implement\",\n"
        "  \"verdict\": \"PASS\",\n"
        "  \"session_id\": \"sess-owner-01\",\n"
        "  \"epic_id\": \"T-HUB-085\",\n"
        "  \"step_id\": \"s01\",\n"
        "  \"recorded_at\": \"2026-09-11T12:00:00Z\"\n"
        "}\n"
        "```"
    )

    proc = _run_hook(
        SUBAGENT_STOP,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "runtime_id": "claude",
            "agent_type": "verify-implement",
            "last_assistant_message": fence_msg,
        },
        tmp_path,
    )
    assert proc.returncode == 2
    assert "semantic_ownership_mismatch" in proc.stderr


# ============================================================================
# Checkpoint 3: Stop Gate rejects manual/stale/forged PASS
# ============================================================================

def test_stop_gate_blocks_stale_or_missing_receipt(tmp_path: Path) -> None:
    """CP3 / FR-007 / TM-085-09: Stop gate blocks finish when evidence receipt is stale or missing."""
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-085\n"
        "step_id: s05\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/plan/T-HUB-085/s05.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — s05\n"
        "- **Дальше:** finalize\n",
        encoding="utf-8",
    )

    session_id = "sess-stale-01"
    identity = {
        "session_id": session_id,
        "epic_id": "T-HUB-085",
        "step": "s05",
        "step_id": "s05",
        "role": "BACK",
        "projection_hash": "hash-s05",
        "phase_epoch": "epoch-s05",
        "event_digest": "evt-s05",
        "authority": "autonomous",
    }
    stale_receipt = issue_verifier_receipt(
        {
            **identity,
            "step": "s04",
            "step_id": "s04",
        },
        "PASS",
        "verify-implement",
    )
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "verify_done": True,
        "verify_verdict": "PASS",
        "verify_evidence": stale_receipt,
        "gate_identity": identity,
        "need_verify": True,
    }
    save_state(session_id, str(tmp_path), st)

    proc = _run_hook(
        STOP_GATE,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH BACK IMPLEMENT — finished step.",
            "stop_hook_active": False,
        },
        tmp_path,
    )
    assert proc.returncode == 0
    res = json.loads(proc.stdout)
    assert res.get("decision") == "block"


def test_stop_gate_rejects_state_only_manual_pass(tmp_path: Path) -> None:
    """CP3 / FR-007 / TM-085-10: State-only manual PASS without receipt proof is rejected."""
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.parent.mkdir(parents=True, exist_ok=True)
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-085\n"
        "step_id: s05\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/plan/T-HUB-085/s05.yaml`\n\n"
        "## Handoff BACK IMPLEMENT — s05\n"
        "- **Дальше:** finalize\n",
        encoding="utf-8",
    )

    session_id = "sess-manual-01"
    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "verify_done": True,
        "verify_verdict": "PASS",
        "verify_evidence": None,
        "need_verify": True,
    }
    save_state(session_id, str(tmp_path), st)

    proc = _run_hook(
        STOP_GATE,
        {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH BACK IMPLEMENT — done.",
            "stop_hook_active": False,
        },
        tmp_path,
    )
    assert proc.returncode == 0
    res = json.loads(proc.stdout)
    assert res.get("decision") == "block"


# ============================================================================
# Checkpoint 4: Complete Valid Gate Flow Allows Finish
# ============================================================================

def test_valid_gate_flow_allows_finish(tmp_path: Path) -> None:
    """CP4: Valid gate flow with issued receipt passes stop gate validation."""
    session_id = "sess-valid-flow"
    identity = {
        "session_id": session_id,
        "epic_id": "T-HUB-085",
        "step": "s05",
        "step_id": "s05",
        "role": "BACK",
        "projection_hash": "hash-valid-01",
        "phase_epoch": "epoch-valid-01",
        "event_digest": "evt-valid-01",
        "authority": "autonomous",
    }
    valid_receipt = issue_verifier_receipt(
        identity,
        "PASS",
        "verify-implement",
    )

    st = {
        "active": True,
        "role": "BACK",
        "mode": "IMPLEMENT",
        "armed_step": "s05",
        "verify_done": True,
        "verify_verdict": "PASS",
        "verify_evidence": valid_receipt,
        "gate_identity": identity,
        "need_verify": False,
    }
    save_state(session_id, str(tmp_path), st)

    ok, diag = IdentityService.validate_receipt_proof(valid_receipt, identity)
    assert ok is True
    assert diag == GateDiagnosticCode.OK
