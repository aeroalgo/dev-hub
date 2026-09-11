from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STOP_GATE = ROOT / ".claude" / "hooks" / "stop-gate.py"
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _ensure_gate_agents(cwd: Path) -> None:
    agents = cwd / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    specs = (
        ("verify", "gate", "pass-fail", True),
        ("reviewer", "gate", "pass-blocked-fail", True),
        ("explorer", "search", "none", False),
    )
    for name, mode, verdict, requires_model in specs:
        path = agents / f"{name}.md"
        if path.is_file():
            continue
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


def _setup_epic_env(cwd: Path) -> None:
    _ensure_gate_agents(cwd)
    mb = cwd / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    decomp = mb / "back" / "plan" / "decompose-T-HUB-022-test"
    decomp.mkdir(parents=True, exist_ok=True)
    (decomp / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\nsteps:\n  - id: s09\n    file: s09.yaml\n    status: active\n",
        encoding="utf-8",
    )
    (cwd / ".claude" / "project.env").write_text(
        "PROJECT_WORKFLOW_HOOKS=always\nPROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    from gate_receipt import issue_verifier_receipt
    from loop.gate_identity import GateIdentity

    session_id = "test"
    state = {
        "active": True,
        "status": "running",
        "session_id": session_id,
        "epic_id": "T-HUB-022",
        "armed_epic": "T-HUB-022",
        "role": "BACK",
        "phase": "BACK IMPLEMENT",
        "armed_step": "s09",
        "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-022-test/index.yaml",
        "pending_fingerprint_before": "old_fp",
        "last_verify_verdict": "PASS",
        "last_finish_tool": {"tool": "mb-finish", "fingerprint": "fp123"},
        "projection_hash": "proj-handoff",
        "phase_epoch": "epoch-handoff",
        "event_digest": "evt-handoff",
    }
    identity = GateIdentity.expected(state, session_id=session_id).to_dict()
    receipt = issue_verifier_receipt(identity, "PASS", "verify-implement")
    state["last_verify_receipt"] = receipt
    state["last_verify_evidence"] = receipt
    state["gate_identity"] = identity
    state_path = cwd / ".claude" / "runtime" / "epic" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")

    spawn_state_path = cwd / ".claude" / "runtime" / "spawn-gate" / "test.json"
    spawn_state_path.parent.mkdir(parents=True, exist_ok=True)
    spawn_state_path.write_text(
        json.dumps(
            {
                "workflow_source": "loop",
                "need_verify": False,
                "verify_done": True,
                "verify_verdict": "PASS",
                "verify_evidence": receipt,
            }
        ),
        encoding="utf-8",
    )


def _run_stop_gate(cwd: Path, payload: dict, env_overrides: dict | None = None) -> dict:
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_") or key in (
            "DEV_HUB",
            "HUB_ROOT",
            "PROJECT_ROOT",
            "CLAUDE_PROJECT_DIR",
        ):
            env.pop(key)
    env["EPIC_LOOP"] = "1"
    if env_overrides:
        for k, v in env_overrides.items():
            env[k] = str(v)
            (cwd / ".claude" / "project.env").write_text(
                f"{k}={v}\nPROJECT_WORKFLOW_HOOKS=loop\nPROJECT_AGENT_VERIFY_MODEL=sonnet\n",
                encoding="utf-8",
            )
    proc = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
    )
    assert proc.returncode == 0, f"stop-gate failed: {proc.stderr}"
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def test_strict_0_legacy_ac_autoproject(tmp_path: Path) -> None:
    _setup_epic_env(tmp_path)
    # Legacy AC without frontmatter
    ac_content = (
        "## load_now\n"
        "1. [s09.yaml](back/plan/decompose-T-HUB-022-test/s09.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s09\n"
        "- **Эпик:** T-HUB-022\n"
        "- **Режим/шаг:** BACK IMPLEMENT s09\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_content, encoding="utf-8")

    # Run with PROJECT_LOOP_HANDOFF_STRICT=0
    res = _run_stop_gate(tmp_path, {"session_id": "test", "cwd": str(tmp_path), "last_assistant_message": "FINISH: done"}, {"PROJECT_LOOP_HANDOFF_STRICT": "0"})
    assert res.get("decision") != "block", f"Expected non-blocked, got: {res}"


def test_strict_1_no_frontmatter_blocked(tmp_path: Path) -> None:
    _setup_epic_env(tmp_path)
    # Legacy AC without frontmatter
    ac_content = (
        "## load_now\n"
        "1. [s09.yaml](back/plan/decompose-T-HUB-022-test/s09.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s09\n"
        "- **Эпик:** T-HUB-022\n"
        "- **Режим/шаг:** BACK IMPLEMENT s09\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_content, encoding="utf-8")

    # Run with PROJECT_LOOP_HANDOFF_STRICT=1
    res = _run_stop_gate(tmp_path, {"session_id": "test", "cwd": str(tmp_path), "last_assistant_message": "FINISH: done"}, {"PROJECT_LOOP_HANDOFF_STRICT": "1"})
    assert res.get("decision") == "block"
    assert "missing_handoff_frontmatter" in res.get("reason", "") or "activeContext shape FAIL" in res.get("reason", "")


def test_strict_1_valid_frontmatter_passes(tmp_path: Path) -> None:
    _setup_epic_env(tmp_path)
    # AC with valid frontmatter including role
    ac_content = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "epic_id: T-HUB-022\n"
        "mode: IMPLEMENT\n"
        "step_id: s09\n"
        "---\n\n"
        "## load_now\n"
        "1. [s09.yaml](back/plan/decompose-T-HUB-022-test/s09.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s09\n"
        "- **Эпик:** T-HUB-022\n"
        "- **Режим/шаг:** BACK IMPLEMENT s09\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_content, encoding="utf-8")

    # Run with PROJECT_LOOP_HANDOFF_STRICT=1
    res = _run_stop_gate(tmp_path, {"session_id": "test", "cwd": str(tmp_path), "last_assistant_message": "FINISH: done"}, {"PROJECT_LOOP_HANDOFF_STRICT": "1"})
    assert res.get("decision") != "block", f"Expected non-blocked, got: {res}"


def test_strict_1_invalid_schema_blocked(tmp_path: Path) -> None:
    _setup_epic_env(tmp_path)
    ac_content = (
        "---\n"
        "schema: unknown-schema/v1\n"
        "role: BACK\n"
        "epic_id: T-HUB-022\n"
        "mode: IMPLEMENT\n"
        "step_id: s09\n"
        "---\n\n"
        "## load_now\n"
        "1. [s09.yaml](back/plan/decompose-T-HUB-022-test/s09.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s09\n"
        "- **Эпик:** T-HUB-022\n"
        "- **Режим/шаг:** BACK IMPLEMENT s09\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_content, encoding="utf-8")

    res = _run_stop_gate(tmp_path, {"session_id": "test", "cwd": str(tmp_path), "last_assistant_message": "FINISH: done"}, {"PROJECT_LOOP_HANDOFF_STRICT": "1"})
    assert res.get("decision") == "block"
    assert "handoff_frontmatter_schema_invalid" in res.get("reason", "")


def test_strict_1_invalid_role_blocked(tmp_path: Path) -> None:
    _setup_epic_env(tmp_path)
    ac_content = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: INVALID_ROLE\n"
        "epic_id: T-HUB-022\n"
        "mode: IMPLEMENT\n"
        "step_id: s09\n"
        "---\n\n"
        "## load_now\n"
        "1. [s09.yaml](back/plan/decompose-T-HUB-022-test/s09.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s09\n"
        "- **Эпик:** T-HUB-022\n"
        "- **Режим/шаг:** BACK IMPLEMENT s09\n"
    )
    (tmp_path / "memory-bank" / "activeContext.md").write_text(ac_content, encoding="utf-8")

    res = _run_stop_gate(tmp_path, {"session_id": "test", "cwd": str(tmp_path), "last_assistant_message": "FINISH: done"}, {"PROJECT_LOOP_HANDOFF_STRICT": "1"})
    assert res.get("decision") == "block"
    assert "handoff_frontmatter_invalid" in res.get("reason", "")


def test_validate_handoff_frontmatter_diagnostics_characterization() -> None:
    """Characterize validate_handoff_frontmatter denial diagnostics."""
    from loop.schemas.active_context import validate_handoff_frontmatter

    # Missing frontmatter
    meta, errs = validate_handoff_frontmatter("plain markdown text without frontmatter")
    assert meta is None
    assert "missing_handoff_frontmatter" in errs

    # Invalid schema name
    invalid_schema = "---\nschema: invalid-schema\nrole: BACK\nmode: IMPLEMENT\nepic_id: T-001\n---\n"
    meta, errs = validate_handoff_frontmatter(invalid_schema)
    assert meta is None
    assert "handoff_frontmatter_schema_invalid" in errs

    # Invalid field value
    invalid_field = "---\nschema: loop-handoff/v1\nrole: UNKNOWN_ROLE\nmode: IMPLEMENT\nepic_id: T-001\n---\n"
    meta, errs = validate_handoff_frontmatter(invalid_field)
    assert meta is None
    assert any("role" in err for err in errs)

    # Valid frontmatter
    valid_text = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-001\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
    )
    meta, errs = validate_handoff_frontmatter(valid_text)
    assert len(errs) == 0
    assert meta is not None
    assert meta.epic_id == "T-001"
    assert meta.role == "BACK"
    assert meta.mode == "IMPLEMENT"
    assert meta.step_id == "s01"


def test_match_gate_evidence_characterization() -> None:
    """Characterize match_gate_evidence behavior for manual and receipt evidence."""
    from _lib import match_gate_evidence

    # Non-dict evidence is rejected
    ok, code = match_gate_evidence("invalid_string", {})
    assert ok is False
    assert code == "verdict_evidence_missing"

    # None evidence is rejected
    ok, code = match_gate_evidence(None, {})
    assert ok is False
    assert code == "verdict_evidence_missing"

    # Manual authority is accepted with non-authoritative fallback
    ok, code = match_gate_evidence({"authority": "manual"}, {})
    assert ok is True
    assert code == "manual_fallback_non_authoritative"

    # Missing identity fields in evidence
    ok, code = match_gate_evidence({"step": "s01"}, {"step": "s01", "projection_hash": "h1", "phase_epoch": "e1"})
    assert ok is False
    assert code == "verdict_identity_missing"

    # Missing identity fields in current projection
    ok, code = match_gate_evidence({"step": "s01", "projection_hash": "h1", "phase_epoch": "e1"}, {"step": "s01"})
    assert ok is False
    assert code == "projection_identity_missing"

    # Matching identity fields
    current = {
        "step": "s01",
        "projection_hash": "h1",
        "phase_epoch": "e1",
        "epic_id": "T-001",
        "role": "BACK",
        "event_digest": "d1",
    }
    evidence = {
        "step": "s01",
        "projection_hash": "h1",
        "phase_epoch": "e1",
        "epic_id": "T-001",
        "role": "BACK",
        "event_digest": "d1",
    }
    ok, code = match_gate_evidence(evidence, current)
    assert ok is True
    assert code == "matched"

    # Step mismatch
    evidence_wrong_step = dict(evidence, step="s02")
    ok, code = match_gate_evidence(evidence_wrong_step, current)
    assert ok is False
    assert code == "verdict_wrong_step"

    # Epoch mismatch
    evidence_wrong_epoch = dict(evidence, phase_epoch="e2")
    ok, code = match_gate_evidence(evidence_wrong_epoch, current)
    assert ok is False
    assert code == "epoch_mismatch"
