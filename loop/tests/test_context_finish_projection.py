"""Tests for context finish projection, mb_finish integration, actor attribution, and corruption handling.

Addresses FR-005, FR-007, FR-008, FR-010.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from harness.hooks.context_ledger import (
    ContextLedger,
    ReadRequest,
    compute_content_hash,
)
from harness.hooks.context_telemetry import (
    build_finish_receipt,
    collect_session_telemetry,
    format_telemetry_summary,
)
from harness.hooks.epic.core import (
    default_state,
    read_active_context,
    save_epic_state,
)
from loop.mb_finish.finish_implement import finish_implement_step
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import (
    HandoffBody,
    LoadNowItem,
    LoopHandoffMeta,
    MbFinishRequest,
)


@pytest.fixture
def epic_env(tmp_path: Path) -> Path:
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-078"
    mb_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-078"
    impl_dir.mkdir(parents=True, exist_ok=True)

    index_yaml = mb_dir / "index.yaml"
    index_yaml.write_text(
        "schema: epic-decompose-index/v1\n"
        "epic_id: T-HUB-078\n"
        "steps:\n"
        "  - id: s04\n"
        "    file: s04-test.yaml\n"
        "    status: in_progress\n"
        "  - id: s05\n"
        "    file: s05-test.yaml\n"
        "    status: pending\n",
        encoding="utf-8",
    )

    s04_decomp = mb_dir / "s04-test.yaml"
    s04_decomp.write_text(
        "schema: epic-decompose/v1\n"
        "role: back\n"
        "step_id: s04\n"
        "plan_id: T-HUB-078\n"
        "title: finish telemetry\n"
        "next_phase: BACK IMPLEMENT\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: telemetry check\n",
        encoding="utf-8",
    )

    s04_impl = impl_dir / "s04-test.yaml"
    s04_impl.write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s04\n"
        "plan_id: T-HUB-078\n"
        "title: finish telemetry\n"
        "status: in_progress\n"
        "date: '2026-09-07'\n"
        "decompose_ref: memory-bank/back/plan/decompose-T-HUB-078/s04-test.yaml\n"
        "skills_used: []\n"
        "discovery: []\n"
        "gaps:\n"
        "  status: none\n"
        "done:\n"
        "  - done item\n"
        "files:\n"
        "  - file1.py\n"
        "deletes: []\n"
        "tests:\n"
        "  - '`timeout 300s .venv/bin/pytest loop/tests/test_context_finish_projection.py`'\n"
        "integration_check:\n"
        "  - ok\n"
        "grep_control: []\n"
        "verification_results: []\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: telemetry check\n"
        "    status: done\n",
        encoding="utf-8",
    )

    act_path = tmp_path / "memory-bank" / "activeContext.md"
    act_content = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-078\n"
        "step_id: s04\n"
        "---\n\n"
        "## load_now\n"
        "1. [s04-test.yaml](back/plan/decompose-T-HUB-078/s04-test.yaml) — test.\n\n"
        "## Handoff BACK IMPLEMENT — s04\n"
        "- **Дальше:** test\n\n"
        "## done\n"
        "- test initial\n"
    )
    act_path.write_text(act_content, encoding="utf-8")

    state = default_state()
    state.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": "T-HUB-078",
            "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-078/index.yaml",
            "armed_step": "s04",
            "armed_role": "BACK",
            "role": "BACK",
            "session_id": "sess-epic-078",
        }
    )
    save_epic_state(tmp_path, state)
    return tmp_path


def test_finish_telemetry_reports_exact_context_counters(epic_env: Path):
    sess_id = "sess-epic-078"
    runtime_dir = epic_env / ".claude" / "runtime"

    file_a = epic_env / "service.py"
    file_a.write_text("def run():\n    pass\n", encoding="utf-8")
    file_b = epic_env / "utils.py"
    file_b.write_text("def helper():\n    pass\n", encoding="utf-8")

    # Root reads
    root_ledger = ContextLedger(
        project_root=epic_env,
        root_session_id=sess_id,
        agent_invocation_id="root",
        runtime_provider="claude",
        actor_kind="root",
        runtime_dir=runtime_dir,
    )
    root_ledger.decide(ReadRequest(str(file_a), compute_content_hash(file_a), [1, 2], "implement"))
    root_ledger.decide(ReadRequest(str(file_a), compute_content_hash(file_a), [1, 2], "implement"))  # duplicate
    root_ledger.decide(ReadRequest(str(file_b), compute_content_hash(file_b), [1, 2], "implement"))
    root_ledger.record_search_exception()

    # Subagent reads
    sub_ledger = ContextLedger(
        project_root=epic_env,
        root_session_id=sess_id,
        agent_invocation_id="sub-verify",
        runtime_provider="claude",
        actor_kind="subagent",
        parent_invocation_id="root",
        runtime_dir=runtime_dir,
    )
    sub_ledger.decide(ReadRequest(str(file_a), compute_content_hash(file_a), [1, 2], "verify"))
    sub_ledger.record_monolith_attempt()

    receipt = build_finish_receipt(epic_env, sess_id, epic_id="T-HUB-078", step_id="s04", runtime_dir=runtime_dir)
    assert receipt.status == "green"
    assert receipt.aggregate.is_green is True
    assert receipt.aggregate.unique_reads == 3
    assert receipt.aggregate.duplicate_reads == 1
    assert receipt.aggregate.search_exceptions == 1
    assert receipt.aggregate.monolith_plan_attempts == 1
    assert receipt.aggregate.highest_repeat_path == "service.py"
    assert receipt.secret_free is True


def test_corrupt_or_missing_ledger_blocks_green_finish(epic_env: Path):
    sess_id = "sess-epic-078"
    runtime_dir = epic_env / ".claude" / "runtime"

    # Corrupt ledger file
    sess_dir = runtime_dir / "context-ledger" / epic_env.name / sess_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    (sess_dir / "root.json").write_text("corrupted content", encoding="utf-8")

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s04",
        done_summary="finished s04 with corrupt ledger",
        cwd=str(epic_env),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify_check, \
         patch("harness.hooks.epic.core._verify_pass_ready_for_step") as mock_verify_fin:
        mock_verify_check.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_verify_fin.return_value = {"ok": True, "diagnostic": "verify_pass"}

        res = finish_implement_step(req)
        assert res.ok is False
        assert any("corrupt" in diag or "telemetry" in diag for diag in res.diagnostic_codes)


def test_root_child_provider_distinguishable_and_deterministic(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    f = proj / "main.py"
    f.write_text("print(42)\n", encoding="utf-8")

    runtime_dir = proj / ".claude" / "runtime"

    # Run sequence for a given session
    def run_seq(sess_id: str):
        r = ContextLedger(proj, sess_id, "root", "claude", "root", runtime_dir=runtime_dir)
        r.decide(ReadRequest(str(f), compute_content_hash(f), [1, 1], "implement"))
        c = ContextLedger(proj, sess_id, "child-1", "codex", "subagent", parent_invocation_id="root", runtime_dir=runtime_dir)
        c.decide(ReadRequest(str(f), compute_content_hash(f), [1, 1], "verify"))
        return build_finish_receipt(proj, sess_id, runtime_dir=runtime_dir)

    receipt1 = run_seq("det-sess-1")
    receipt2 = run_seq("det-sess-2")

    assert receipt1.aggregate.unique_reads == receipt2.aggregate.unique_reads == 2
    assert receipt1.aggregate.duplicate_reads == receipt2.aggregate.duplicate_reads == 0
    assert len(receipt1.aggregate.actors) == len(receipt2.aggregate.actors) == 2
    assert "claude" in receipt1.aggregate.provider_breakdown
    assert "codex" in receipt1.aggregate.provider_breakdown
    assert receipt1.aggregate.provider_breakdown["claude"]["unique_reads"] == receipt2.aggregate.provider_breakdown["claude"]["unique_reads"] == 1
    assert receipt1.aggregate.provider_breakdown["codex"]["unique_reads"] == receipt2.aggregate.provider_breakdown["codex"]["unique_reads"] == 1


def test_telemetry_summary_projected_into_active_context(epic_env: Path):
    sess_id = "sess-epic-078"
    runtime_dir = epic_env / ".claude" / "runtime"

    file_a = epic_env / "service.py"
    file_a.write_text("def run():\n    pass\n", encoding="utf-8")

    root_ledger = ContextLedger(epic_env, sess_id, "root", "claude", "root", runtime_dir=runtime_dir)
    root_ledger.decide(ReadRequest(str(file_a), compute_content_hash(file_a), [1, 1], "implement"))

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s04",
        done_summary="finished s04 with clean telemetry",
        cwd=str(epic_env),
    )

    with patch("loop.mb_finish.finish_implement._verify_pass_ready_for_step") as mock_verify_check, \
         patch("harness.hooks.epic.core._verify_pass_ready_for_step") as mock_verify_fin:
        mock_verify_check.return_value = {"ok": True, "diagnostic": "verify_pass"}
        mock_verify_fin.return_value = {"ok": True, "diagnostic": "verify_pass"}

        res = finish_implement_step(req)
        assert res.ok is True
        assert res.active_context is not None
        assert "- **Context Telemetry:** unique_reads=1" in res.active_context
        assert "(green)" in res.active_context
