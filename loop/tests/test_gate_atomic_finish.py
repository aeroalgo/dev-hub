"""gate_atomic_finish + finish_implement repair + Codex filter stop markers."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import epic_codex_stream_filter as csf  # noqa: E402
from harness.hooks.epic.core import default_state, save_epic_state
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.schemas import MbFinishRequest
from loop.runtime_adapters import subagent_lifecycle as lifecycle


def _setup_implement_desync(tmp_path: Path) -> Path:
    """implement yaml completed while index step still in_progress (s02 incident)."""
    plan = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-GATE" / "yaml"
    plan.mkdir(parents=True)
    steps = plan / "steps"
    steps.mkdir(parents=True)
    impl = tmp_path / "memory-bank" / "back" / "implement" / "T-HUB-GATE"
    impl.mkdir(parents=True)

    (plan / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-GATE\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-test.yaml\n"
        "    status: in_progress\n",
        encoding="utf-8",
    )
    (steps / "s01-test.yaml").write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-GATE\n"
        "title: test\n"
        "next_phase: BACK IMPLEMENT\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: c\n",
        encoding="utf-8",
    )
    (impl / "s01-test.yaml").write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: T-HUB-GATE\n"
        "title: test\n"
        "status: completed\n"
        "date: '2026-09-10'\n"
        "decompose_ref: memory-bank/back/plan/T-HUB-GATE/yaml/steps/s01-test.yaml\n"
        "skills_used: []\n"
        "discovery: []\n"
        "gaps:\n"
        "  status: none\n"
        "done:\n"
        "  - done\n"
        "files:\n"
        "  - a.py\n"
        "deletes: []\n"
        "tests:\n"
        "  - '`timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py`'\n"
        "integration_check:\n"
        "  - ok\n"
        "grep_control: []\n"
        "verification_results: []\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: c\n"
        "    status: done\n",
        encoding="utf-8",
    )
    act = tmp_path / "memory-bank" / "activeContext.md"
    act.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-GATE\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "1. [s01](back/plan/T-HUB-GATE/yaml/steps/s01-test.yaml) — t.\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Дальше:** t\n\n"
        "## done\n"
        "- x\n",
        encoding="utf-8",
    )
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": "T-HUB-GATE",
            "armed_decompose": "memory-bank/back/plan/T-HUB-GATE/yaml/decompose-index.yaml",
            "armed_step": "s01",
            "armed_role": "BACK",
            "role": "BACK",
            "phase_run_id": "run-gate",
            "last_verify_verdict": "PASS",
            "last_verify_evidence": {
                "schema": "loop-verifier-receipt/v1",
                "session_id": "sess-gate",
                "phase_epoch": "sha256:a",
                "projection_hash": "sha256:b",
                "event_digest": "sha256:c",
                "epic_id": "T-HUB-GATE",
                "role": "BACK",
                "step": "s01",
                "verifier_identity": "verify-implement",
                "verdict": "PASS",
                "created_at": "2026-09-10T00:00:00Z",
                "authority": "autonomous",
                "receipt_digest": "sha256:d",
                "diagnostic": "matched",
                "valid": True,
            },
            "last_verify_evidence_sha256": "sha256:d",
            "last_verify_receipt": {
                "schema": "loop-verifier-receipt/v1",
                "session_id": "sess-gate",
                "phase_epoch": "sha256:a",
                "projection_hash": "sha256:b",
                "event_digest": "sha256:c",
                "epic_id": "T-HUB-GATE",
                "role": "BACK",
                "step": "s01",
                "verifier_identity": "verify-implement",
                "verdict": "PASS",
                "created_at": "2026-09-10T00:00:00Z",
                "authority": "autonomous",
                "receipt_digest": "sha256:d",
                "diagnostic": "matched",
                "valid": True,
            },
        }
    )
    save_epic_state(tmp_path, st)
    return tmp_path


def test_finish_implement_repairs_mark_index_missing(tmp_path, monkeypatch) -> None:
    cwd = _setup_implement_desync(tmp_path)

    monkeypatch.setattr(
        "loop.mb_finish.finish_implement._verify_pass_ready_for_step",
        lambda *a, **k: {"ok": True, "diagnostic": "verify_pass"},
    )
    monkeypatch.setattr(
        "harness.hooks.epic.core._verify_pass_ready_for_step",
        lambda *a, **k: {"ok": True, "diagnostic": "verify_pass"},
    )

    res = finish_implement_step(
        MbFinishRequest(
            cwd=str(cwd),
            phase="IMPLEMENT",
            step_id="s01",
            done_summary="repaired finish",
        )
    )
    assert res.ok, f"{res.diagnostic_codes} {res.shape_errors}"
    index = (cwd / "memory-bank/back/plan/T-HUB-GATE/yaml/decompose-index.yaml").read_text()
    assert "status: completed" in index
    impl = (cwd / "memory-bank/back/implement/T-HUB-GATE/s01-test.yaml").read_text()
    assert "status: completed" in impl


def test_codex_filter_emits_stop_on_finish_ok(monkeypatch) -> None:
    class _Action:
        agent_type = "verify-implement"
        verdict = "PASS"
        start_exit_code = 0
        stop_exit_code = 0
        finish = {"ok": True, "already_finished": True}
        stderr = ""

    class _Life:
        def process_item(self, item):
            return [_Action()]

    monkeypatch.setattr(csf, "_lifecycle", _Life())
    buf = io.StringIO()
    with redirect_stdout(buf):
        csf.emit_from_obj(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "child-1": {"status": "completed", "message": "done"}
                    },
                },
            }
        )
    out = buf.getvalue()
    assert "automatic mb-finish completed; stop current turn" in out


def test_codex_filter_emits_diagnostic_on_finish_fail(monkeypatch) -> None:
    class _Action:
        agent_type = "verify-implement"
        verdict = "PASS"
        start_exit_code = 0
        stop_exit_code = 0
        finish = {
            "ok": False,
            "diagnostic_codes": ["verify_pass_missing"],
            "error": "verify PASS required",
        }
        stderr = ""

    class _Life:
        def process_item(self, item):
            return [_Action()]

    monkeypatch.setattr(csf, "_lifecycle", _Life())
    buf = io.StringIO()
    with redirect_stdout(buf):
        csf.emit_from_obj(
            {
                "type": "item.completed",
                "item": {
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "child-1": {"status": "completed", "message": "done"}
                    },
                },
            }
        )
    out = buf.getvalue()
    assert "automatic mb-finish did not complete" in out
    assert "verify_pass_missing" in out
    assert "core.py" not in out
