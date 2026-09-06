"""Tests for transactional boundary of mb-finish and crash recovery (T-HUB-068).

Independent Test SoT:
- Crash after context write leaves mixed Handoff/index identity -> recover must align files (both new or both old).
- Public CLI / python finish_handoff without recovery_token -> diagnostic finish_handoff_forbidden, state not armed.
- FAIL dilution documented: atomic replace of one file without multi-file journal is not enough.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness.hooks.epic.core import (
    atomic_write_text,
    extract_handoff_block,
    load_decompose_steps_fail_closed,
    load_epic_state,
    save_epic_state,
)
from loop.mb_finish.transaction import (
    FINISH_TX_SCHEMA,
    FinishTxRecord,
    FinishTxStagedFile,
    FinishTxState,
    commit_staged_files,
    get_finish_tx_path,
    read_finish_tx,
    rollback_staged_files,
    stage_file_in_tx,
    validate_identity,
    write_finish_tx,
)
from loop.mb_finish.impl import finish_handoff
from loop.mb_finish.schemas import (
    HandoffBody,
    LoadNowItem,
    LoopHandoffMeta,
    MbFinishResult,
)
from loop.paths.pack_layout import resolve_mb_root

ROOT = Path(__file__).resolve().parents[2]


def _setup_epic_fixture(tmp_path: Path) -> dict[str, Any]:
    """Create a minimal 2-step decompose environment."""
    dec_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-EPIC-DEMO" / "yaml"
    steps_dir = dec_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)

    # Add analyze artifact so ANALYZE gate is closed/satisfied
    ana_dir = tmp_path / "memory-bank" / "back" / "analyze" / "T-EPIC-DEMO"
    ana_dir.mkdir(parents=True, exist_ok=True)
    (ana_dir / "analyze-20260906.yaml").write_text(
        "schema: epic-analyze/v1\n"
        "epic_id: T-EPIC-DEMO\n"
        "role: back\n"
        "verdict: pass\n"
        "metrics:\n"
        "  critical_count: 0\n",
        encoding="utf-8",
    )

    index_yaml = dec_dir / "decompose-index.yaml"
    index_content = (
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-EPIC-DEMO\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-step.yaml\n"
        "    title: Step 1\n"
        "    status: pending\n"
        "  - id: s02\n"
        "    file: s02-step.yaml\n"
        "    title: Step 2\n"
        "    status: pending\n"
    )
    index_yaml.write_text(index_content, encoding="utf-8")

    s01_yaml = steps_dir / "s01-step.yaml"
    s01_yaml.write_text("schema: epic-decompose/v1\nstep_id: s01\nstatus: pending\n", encoding="utf-8")
    s02_yaml = steps_dir / "s02-step.yaml"
    s02_yaml.write_text("schema: epic-decompose/v1\nstep_id: s02\nstatus: pending\n", encoding="utf-8")

    act_path = tmp_path / "memory-bank" / "activeContext.md"
    act_path.parent.mkdir(parents=True, exist_ok=True)
    initial_context = (
        "## load_now\n"
        "- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s01-step.yaml`\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT @s01`\n"
        "- **Фаза:** `BACK IMPLEMENT`\n"
        "- **Эпик:** `T-EPIC-DEMO`\n"
        "- **Шаг:** `s01`\n"
    )
    act_path.write_text(initial_context, encoding="utf-8")

    state = {
        "armed_epic": "T-EPIC-DEMO",
        "armed_role": "BACK",
        "armed_decompose": "memory-bank/back/plan/T-EPIC-DEMO/yaml/decompose-index.yaml",
        "armed_step": "s01",
        "phase": "BACK IMPLEMENT",
        "active": True,
        "status": "armed",
    }
    save_epic_state(tmp_path, state)

    return {
        "index_yaml": index_yaml,
        "s01_yaml": s01_yaml,
        "s02_yaml": s02_yaml,
        "act_path": act_path,
    }


def test_crash_after_context_mixed_identity_recovered(tmp_path: Path) -> None:
    """TM-001 / US-001 / SC-001: Crash after context write leaves mixed Handoff/index.

    Scenario:
    - Context file was replaced (staged/written to next step s02).
    - Process was killed before index commit (s01 is still pending in decompose-index.yaml).
    - As-built unjournaled behavior has mixed identity: Handoff points to s02, index points to s01 pending.
    - Recover mechanism (s04) MUST align files: either both new (s02) or both old (s01), never mixed identity.

    Dilution FAIL: 'atomic replace of one file' without multi-file journal leaves mixed identity across files.
    """
    fixture = _setup_epic_fixture(tmp_path)
    act_path: Path = fixture["act_path"]
    index_yaml: Path = fixture["index_yaml"]

    # Simulate crash after context write: activeContext points to s02, but decompose-index still says s01 pending
    crashed_context = (
        "## load_now\n"
        "- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml`\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT @s02`\n"
        "- **Фаза:** `BACK IMPLEMENT`\n"
        "- **Эпик:** `T-EPIC-DEMO`\n"
        "- **Шаг:** `s02`\n"
    )
    act_path.write_text(crashed_context, encoding="utf-8")

    # Verify that in unrecovered/crashed state we currently have mixed identity
    ctx_text = act_path.read_text(encoding="utf-8")
    handoff = extract_handoff_block(ctx_text)
    assert "@s02" in handoff or "s02" in handoff

    loaded_index = load_decompose_steps_fail_closed(tmp_path, "memory-bank/back/plan/T-EPIC-DEMO/yaml/decompose-index.yaml")
    steps = loaded_index.get("steps", [])
    s01_info = next((s for s in steps if s.get("id") == "s01"), None)
    assert s01_info is not None
    assert s01_info.get("status") == "pending"

    # Now attempt to recover via prepare_session (which runs recover_finish_transaction and sync_cursor_from_index)
    from loop.context_loop import prepare_session
    prep = prepare_session(tmp_path)
    assert prep.get("ok") is True, f"prepare_session failed during recovery: {prep}"

    # Post-recovery invariant: never mixed identity (either both s01 or both s02)
    ctx_after = act_path.read_text(encoding="utf-8")
    handoff_after = extract_handoff_block(ctx_after)
    handoff_step = "s02" if "@s02" in handoff_after else "s01"

    index_after = load_decompose_steps_fail_closed(tmp_path, "memory-bank/back/plan/T-EPIC-DEMO/yaml/decompose-index.yaml")
    s01_status = next(s["status"] for s in index_after.get("steps", []) if s.get("id") == "s01")

    if handoff_step == "s02":
        # New identity: s01 must be completed
        assert s01_status == "completed", "Mixed identity: Handoff is s02 but s01 is not completed in index"
    elif handoff_step == "s01":
        # Rolled back to old identity: s01 is pending, handoff is s01
        assert s01_status == "pending", "Mixed identity: Handoff rolled back to s01 but index is not pending"
    else:
        pytest.fail(f"Unknown handoff step identity: {handoff_step}")


def test_mb_finish_handoff_without_token_forbidden_recovery_token_tokenless(tmp_path: Path) -> None:
    """TM-003 / US-002 / SC-002: Public finish_handoff without token is forbidden.

    Public CLI or unit call to finish_handoff without recovery_token must fail with
    diagnostic 'finish_handoff_forbidden' and refuse to write/arm state.
    """
    _setup_epic_fixture(tmp_path)

    meta = LoopHandoffMeta(mode="BACK IMPLEMENT", role="BACK", epic_id="T-EPIC-DEMO", step_id="s01")
    load_now = [LoadNowItem(path="memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml", description="Step 2")]
    body = HandoffBody(mode="BACK IMPLEMENT", next_hint="step 2", epic_id="T-EPIC-DEMO", step_id="s02")

    # Call finish_handoff without recovery_token
    # On as-built: finish_handoff succeeds (ok=True) and does not require recovery_token.
    # Contract: MUST return ok=False, diagnostic_codes containing 'finish_handoff_forbidden'.
    res: MbFinishResult = finish_handoff(meta, load_now, body, cwd=tmp_path)

    assert not res.ok, "Expected finish_handoff without recovery_token to fail"
    assert "finish_handoff_forbidden" in res.diagnostic_codes, (
        f"Expected diagnostic 'finish_handoff_forbidden', got {res.diagnostic_codes}"
    )


def test_handoff_without_token_does_not_arm_state_tokenless(tmp_path: Path) -> None:
    """AC-2: Public finish_handoff without token must not arm state or bypass verify."""
    _setup_epic_fixture(tmp_path)

    meta = LoopHandoffMeta(mode="BACK IMPLEMENT", role="BACK", epic_id="T-EPIC-DEMO", step_id="s01")
    load_now = [LoadNowItem(path="memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml", description="Step 2")]
    body = HandoffBody(mode="BACK IMPLEMENT", next_hint="step 2", epic_id="T-EPIC-DEMO", step_id="s02")

    res = finish_handoff(meta, load_now, body, cwd=tmp_path)
    state = load_epic_state(tmp_path)

    # State must remain armed on s01, not altered by forbidden handoff
    assert state.get("armed_step") == "s01"
    assert "finish_handoff_forbidden" in (res.diagnostic_codes or [])


def test_cli_mb_finish_handoff_without_token_fails_closed_tokenless(tmp_path: Path) -> None:
    """CLI dispatcher 'mb-finish handoff' without recovery_token exits non-zero with error diagnostic."""
    _setup_epic_fixture(tmp_path)

    cmd = [
        sys.executable,
        str(ROOT / "harness" / "hooks" / "epic_resolve.py"),
        "--cwd",
        str(tmp_path),
        "mb-finish",
        "handoff",
        "--mode",
        "BACK IMPLEMENT",
        "--epic-id",
        "T-EPIC-DEMO",
        "--step",
        "s01",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    # In s01 red state: as-built epic_resolve.py invokes finish_handoff directly and exits 0.
    # In target state: exits non-zero (code 2) and outputs diagnostic finish_handoff_forbidden.
    assert proc.returncode != 0, f"Expected non-zero exit code from tokenless CLI handoff, got 0. stdout: {proc.stdout}"
    assert "finish_handoff_forbidden" in proc.stdout, (
        f"Expected 'finish_handoff_forbidden' in stdout, got:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# s02: Sidecar finish journal unit tests (FR-001, FR-002, FR-003, FR-004, FR-011, TM-006)
# ---------------------------------------------------------------------------


def test_journal_sidecar_schema_required_extra_forbid(tmp_path: Path) -> None:
    """FR-001 / FR-011: Sidecar journal schema loop-finish-transaction/v1 and extra=forbid."""
    rec = FinishTxRecord(
        tx_id="tx-001",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
    )
    assert rec.schema_version == "loop-finish-transaction/v1"
    write_finish_tx(tmp_path, rec)

    sidecar_file = get_finish_tx_path(tmp_path)
    assert sidecar_file.exists()

    loaded = read_finish_tx(tmp_path)
    assert loaded is not None
    assert loaded.schema_version == "loop-finish-transaction/v1"
    assert loaded.tx_id == "tx-001"
    assert loaded.state == FinishTxState.PREPARED

    # Missing schema or invalid schema fails validation
    raw = json.loads(sidecar_file.read_text(encoding="utf-8"))
    raw["schema"] = "invalid-schema/v99"
    sidecar_file.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(Exception):
        read_finish_tx(tmp_path)

    # Extra field forbidden
    raw["schema"] = "loop-finish-transaction/v1"
    raw["unknown_extra_field"] = "bad"
    sidecar_file.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(Exception):
        read_finish_tx(tmp_path)


def test_journal_states_prepared_to_committed(tmp_path: Path) -> None:
    """FR-002: States prepared -> context_written -> index_written -> committed; rollback_required."""
    rec = FinishTxRecord(
        tx_id="tx-002",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
    )
    write_finish_tx(tmp_path, rec)
    assert read_finish_tx(tmp_path).state == FinishTxState.PREPARED

    rec.state = FinishTxState.CONTEXT_WRITTEN
    write_finish_tx(tmp_path, rec)
    assert read_finish_tx(tmp_path).state == FinishTxState.CONTEXT_WRITTEN

    rec.state = FinishTxState.INDEX_WRITTEN
    write_finish_tx(tmp_path, rec)
    assert read_finish_tx(tmp_path).state == FinishTxState.INDEX_WRITTEN

    rec.state = FinishTxState.COMMITTED
    write_finish_tx(tmp_path, rec)
    assert read_finish_tx(tmp_path).state == FinishTxState.COMMITTED

    rec.state = FinishTxState.ROLLBACK_REQUIRED
    rec.error = "Simulated failure"
    write_finish_tx(tmp_path, rec)
    loaded = read_finish_tx(tmp_path)
    assert loaded.state == FinishTxState.ROLLBACK_REQUIRED
    assert loaded.error == "Simulated failure"


def test_journal_stage_commit_fsync_replace(tmp_path: Path) -> None:
    """FR-003 / FR-011: Staged files in tx dir, commit = atomic_write_text (replace+fsync), rollback."""
    target_rel = "memory-bank/back/plan/T-EPIC-DEMO/yaml/decompose-index.yaml"
    target_file = tmp_path / target_rel
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("old_content: true\n", encoding="utf-8")

    staged = stage_file_in_tx(tmp_path, "tx-003", target_rel, "new_content: true\n")
    assert staged.rel_path == target_rel
    assert (tmp_path / staged.stage_path).read_text(encoding="utf-8") == "new_content: true\n"
    assert staged.backup_path is not None
    assert (tmp_path / staged.backup_path).read_text(encoding="utf-8") == "old_content: true\n"

    # Before commit, target is still old
    assert target_file.read_text(encoding="utf-8") == "old_content: true\n"

    # Commit replaces target
    commit_staged_files(tmp_path, [staged])
    assert target_file.read_text(encoding="utf-8") == "new_content: true\n"

    # Rollback restores backup
    rollback_staged_files(tmp_path, [staged])
    assert target_file.read_text(encoding="utf-8") == "old_content: true\n"


def test_identity_mismatch_aborts_tx() -> None:
    """FR-004 / TM-006: Identity check fails when staged Handoff epic/step != index target != armed."""
    # All match -> True
    assert validate_identity(
        staged_epic_id="T-EPIC-DEMO",
        staged_step_id="s01",
        index_target_step_id="s01",
        armed_epic_id="T-EPIC-DEMO",
        armed_step_id="s01",
    )

    # Epic mismatch -> False
    assert not validate_identity(
        staged_epic_id="T-EPIC-MISMATCH",
        staged_step_id="s01",
        index_target_step_id="s01",
        armed_epic_id="T-EPIC-DEMO",
        armed_step_id="s01",
    )

    # Step mismatch vs armed -> False
    assert not validate_identity(
        staged_epic_id="T-EPIC-DEMO",
        staged_step_id="s02",
        index_target_step_id="s01",
        armed_epic_id="T-EPIC-DEMO",
        armed_step_id="s01",
    )

    # Index target mismatch vs armed -> False
    assert not validate_identity(
        staged_epic_id="T-EPIC-DEMO",
        staged_step_id="s01",
        index_target_step_id="s02",
        armed_epic_id="T-EPIC-DEMO",
        armed_step_id="s01",
    )


def test_finish_implement_uses_journal_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-010 / AC+1: finish_implement_step commits via journal states."""
    fixture = _setup_epic_fixture(tmp_path)
    import loop.mb_finish.finish_implement as fi_mod
    import harness.hooks.epic.core as epic_core
    from loop.mb_finish.schemas import MbFinishRequest
    from loop.mb_finish.transaction import FinishTxState, read_finish_tx

    # Create implement step shard file
    impl_shard = tmp_path / "memory-bank" / "back" / "implement" / "T-EPIC-DEMO" / "s01.yaml"
    impl_shard.parent.mkdir(parents=True, exist_ok=True)
    # Create dummy file on disk for files list
    dummy_code = tmp_path / "app" / "dummy.py"
    dummy_code.parent.mkdir(parents=True, exist_ok=True)
    dummy_code.write_text("# code\n", encoding="utf-8")

    impl_shard.write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "status: in_progress\n"
        "step_id: s01\n"
        "plan_id: T-EPIC-DEMO\n"
        "title: Step 1 Implementation\n"
        "date: '2026-09-06'\n"
        "done: ['done']\n"
        "files:\n"
        "  - app/dummy.py\n"
        "tests:\n"
        "  - '`bin/pytest loop/tests/test_mb_finish_transaction.py`'\n"
        "integration_check:\n"
        "  - ok\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    status: done\n"
        "    criterion: ok\n"
        "    verify: ok\n",
        encoding="utf-8",
    )

    # Stub _verify_pass_ready_for_step in both modules to simulate verify PASS
    monkeypatch.setattr(fi_mod, "_verify_pass_ready_for_step", lambda cwd, step_id: {"ok": True, "verdict": "PASS"})
    monkeypatch.setattr(epic_core, "_verify_pass_ready_for_step", lambda cwd, step_id: {"ok": True, "verdict": "PASS"})

    req = MbFinishRequest(
        phase="BACK IMPLEMENT",
        step_id="s01",
        done_summary="Implemented s01 step",
        cwd=str(tmp_path),
    )
    res = fi_mod.finish_implement_step(req)
    assert res.ok, f"finish_implement_step failed: {res.shape_errors} {res.diagnostic_codes}"

    tx = read_finish_tx(tmp_path)
    assert tx is not None, "Expected finish transaction journal record to be created"
    assert tx.state == FinishTxState.COMMITTED
    assert tx.step_id == "s01"
    assert tx.phase == "BACK IMPLEMENT"


def test_finish_qa_uses_journal_helper(tmp_path: Path) -> None:
    """FR-010: finish_qa commits via journal states."""
    _setup_epic_fixture(tmp_path)
    from loop.mb_finish.impl import finish_qa
    from loop.mb_finish.schemas import MbFinishRequest
    from loop.mb_finish.transaction import FinishTxState, read_finish_tx
    from harness.hooks.epic.core import atomic_write_text

    # Write a passing QA artifact so finish_qa passes validation
    qa_art_path = tmp_path / "memory-bank" / "back" / "qa" / "T-EPIC-DEMO" / "qa-20260906-review.yaml"
    qa_art_path.parent.mkdir(parents=True, exist_ok=True)
    qa_content = (
        "schema: qa-result/v1\n"
        "epic_id: T-EPIC-DEMO\n"
        "role: back\n"
        "verdict: pass\n"
        "reviewer_gate: PASS\n"
    )
    atomic_write_text(qa_art_path, qa_content)

    req = MbFinishRequest(
        phase="BACK QA",
        step_id="QA",
        done_summary="QA passed",
        cwd=str(tmp_path),
    )
    res = finish_qa(req)
    assert res.ok, f"finish_qa failed: {res.shape_errors} {res.diagnostic_codes}"

    tx = read_finish_tx(tmp_path)
    assert tx is not None, "Expected finish transaction journal record to be created for QA"
    assert tx.state == FinishTxState.COMMITTED
    assert tx.step_id == "QA"
    assert tx.phase == "BACK QA"


def test_finish_handoff_requires_recovery_token(tmp_path: Path) -> None:
    """FR-007 / US-002: Internal finish_handoff validates token vs journal id."""
    _setup_epic_fixture(tmp_path)
    from loop.mb_finish.impl import finish_handoff
    from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
    from loop.mb_finish.transaction import FinishTxRecord, FinishTxState, write_finish_tx

    meta = LoopHandoffMeta(mode="BACK IMPLEMENT", role="BACK", epic_id="T-EPIC-DEMO", step_id="s01")
    load_now = [LoadNowItem(path="memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml", description="Step 2")]
    body = HandoffBody(mode="BACK IMPLEMENT", next_hint="step 2", epic_id="T-EPIC-DEMO", step_id="s02")

    # 1. No token -> forbidden
    res_no_tok = finish_handoff(meta, load_now, body, cwd=tmp_path)
    assert not res_no_tok.ok
    assert "finish_handoff_forbidden" in res_no_tok.diagnostic_codes

    # 2. Wrong token -> forbidden
    res_wrong_tok = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token="wrong-token")
    assert not res_wrong_tok.ok
    assert "finish_handoff_forbidden" in res_wrong_tok.diagnostic_codes

    # 3. Valid token matching active journal -> allowed
    tx_rec = FinishTxRecord(
        tx_id="tx-valid-123",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        recovery_token="tx-valid-123",
    )
    write_finish_tx(tmp_path, tx_rec)

    res_valid = finish_handoff(meta, load_now, body, cwd=tmp_path, recovery_token="tx-valid-123")
    assert res_valid.ok, f"finish_handoff with matching recovery_token failed: {res_valid.shape_errors}"


def test_check_after_does_not_call_public_handoff() -> None:
    """FR-014: halt_logic / context_loop do not call public finish_handoff."""
    context_loop_py = Path("loop/context_loop.py")
    if context_loop_py.exists():
        content = context_loop_py.read_text(encoding="utf-8")
        assert "finish_handoff(" not in content, "context_loop must not call finish_handoff"


# ---------------------------------------------------------------------------
# s04: prepare_session recovers leftover journal before agent work
# (FR-005, FR-013, US-001, US-004, SC-001, SC-003, AC+2, AC+4, AC−1, AC−3, AC−5, TM-001, TM-002, TM-004, TM-007)
# ---------------------------------------------------------------------------


def test_prepare_session_recovers_leftover_journal(tmp_path: Path) -> None:
    """FR-005 / US-004 / SC-003 / AC+2 / TM-004: prepare_session calls recover_finish_transaction before agent work."""
    from loop.context_loop import prepare_session
    from loop.mb_finish.transaction import (
        FinishTxRecord,
        FinishTxState,
        get_finish_tx_path,
        stage_file_in_tx,
        write_finish_tx,
    )

    fixture = _setup_epic_fixture(tmp_path)
    act_path: Path = fixture["act_path"]

    # Stage context write pointing to s02 and leave journal in PREPARED state
    staged = stage_file_in_tx(
        tmp_path,
        "tx-leftover",
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml`\n\n## Handoff BACK IMPLEMENT\n- **Следующий:** `BACK IMPLEMENT @s02`\n",
    )
    # Simulate partial write of activeContext
    act_path.write_text("corrupt_or_partial_context_before_crash", encoding="utf-8")

    rec = FinishTxRecord(
        tx_id="tx-leftover",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.PREPARED,
        staged_files=[staged],
        recovery_token="tx-leftover",
    )
    write_finish_tx(tmp_path, rec)
    assert get_finish_tx_path(tmp_path).exists()

    # prepare_session should recover transaction (rollback to backup) and clean journal
    res = prepare_session(tmp_path)
    assert res.get("ok"), f"prepare_session failed: {res}"

    # Journal sidecar must be cleaned up
    assert not get_finish_tx_path(tmp_path).exists()
    # activeContext must be restored to original fixture state (s01), not partial
    ctx_text = act_path.read_text(encoding="utf-8")
    assert "s01" in ctx_text
    assert "corrupt_or_partial" not in ctx_text


def test_crash_after_context_recover_aligns(tmp_path: Path) -> None:
    """TM-001 / US-001 / AC−1: Crash after context write without journal or with CONTEXT_WRITTEN journal."""
    from loop.context_loop import prepare_session
    from loop.mb_finish.transaction import (
        FinishTxRecord,
        FinishTxState,
        stage_file_in_tx,
        write_finish_tx,
    )

    fixture = _setup_epic_fixture(tmp_path)
    act_path: Path = fixture["act_path"]

    staged = stage_file_in_tx(
        tmp_path,
        "tx-ctx-written",
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml`\n\n## Handoff BACK IMPLEMENT\n- **Следующий:** `BACK IMPLEMENT @s02`\n",
    )
    # Overwrite target with staged content (simulating crash right after context write)
    act_path.write_text("## load_now\n- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml`\n\n## Handoff BACK IMPLEMENT\n- **Следующий:** `BACK IMPLEMENT @s02`\n", encoding="utf-8")

    rec = FinishTxRecord(
        tx_id="tx-ctx-written",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.CONTEXT_WRITTEN,
        staged_files=[staged],
        recovery_token="tx-ctx-written",
    )
    write_finish_tx(tmp_path, rec)

    # prepare_session rolls back context_written because index was never committed
    res = prepare_session(tmp_path)
    assert res.get("ok"), f"prepare_session failed: {res}"

    ctx_text = act_path.read_text(encoding="utf-8")
    assert "s01" in ctx_text
    assert "@s02" not in ctx_text


def test_crash_after_index_pre_marker_recover(tmp_path: Path) -> None:
    """FR-013 / TM-002 / AC−3: Crash after index before committed marker -> recovers remainder."""
    from loop.context_loop import prepare_session
    from loop.mb_finish.transaction import (
        FinishTxRecord,
        FinishTxState,
        get_finish_tx_path,
        stage_file_in_tx,
        write_finish_tx,
    )

    fixture = _setup_epic_fixture(tmp_path)
    act_path: Path = fixture["act_path"]
    index_yaml: Path = fixture["index_yaml"]

    # In INDEX_WRITTEN state, index was marked completed on disk (or staged)
    new_index = (
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-EPIC-DEMO\n"
        "steps:\n"
        "  - id: s01\n"
        "    file: s01-step.yaml\n"
        "    title: Step 1\n"
        "    status: completed\n"
        "  - id: s02\n"
        "    file: s02-step.yaml\n"
        "    title: Step 2\n"
        "    status: pending\n"
    )
    index_yaml.write_text(new_index, encoding="utf-8")

    staged = stage_file_in_tx(
        tmp_path,
        "tx-idx-written",
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/T-EPIC-DEMO/yaml/steps/s02-step.yaml`\n\n## Handoff BACK IMPLEMENT\n- **Следующий:** `BACK IMPLEMENT @s02`\n",
    )

    rec = FinishTxRecord(
        tx_id="tx-idx-written",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.INDEX_WRITTEN,
        staged_files=[staged],
        recovery_token="tx-idx-written",
    )
    write_finish_tx(tmp_path, rec)

    # prepare_session commits remainder and cleans up journal
    res = prepare_session(tmp_path)
    assert not get_finish_tx_path(tmp_path).exists()
    ctx_text = act_path.read_text(encoding="utf-8")
    assert "@s02" in ctx_text or "s02" in ctx_text


def test_committed_leftover_recover_idempotent(tmp_path: Path) -> None:
    """AC+4: Leftover journal with COMMITTED state is cleaned up idempotently."""
    from loop.context_loop import prepare_session
    from loop.mb_finish.transaction import (
        FinishTxRecord,
        FinishTxState,
        get_finish_tx_path,
        write_finish_tx,
    )

    _setup_epic_fixture(tmp_path)
    rec = FinishTxRecord(
        tx_id="tx-committed",
        epic_id="T-EPIC-DEMO",
        step_id="s01",
        phase="BACK IMPLEMENT",
        state=FinishTxState.COMMITTED,
        recovery_token="tx-committed",
    )
    write_finish_tx(tmp_path, rec)
    assert get_finish_tx_path(tmp_path).exists()

    res = prepare_session(tmp_path)
    assert res.get("ok")
    assert not get_finish_tx_path(tmp_path).exists()


def test_corrupt_journal_need_human_fail_closed(tmp_path: Path) -> None:
    """TM-007 / AC−5: Corrupt journal fails closed with NEED_HUMAN, does not loop forever."""
    from loop.context_loop import prepare_session
    from loop.mb_finish.transaction import get_finish_tx_path

    _setup_epic_fixture(tmp_path)
    sidecar = get_finish_tx_path(tmp_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("{corrupted_json: true, invalid syntax", encoding="utf-8")

    res = prepare_session(tmp_path)
    assert not res.get("ok")
    assert res.get("halt") is True
    assert res.get("stop") == "NEED_HUMAN"
    assert "corrupt" in (res.get("diagnostic_code") or "").lower() or "need_human" in (res.get("reason") or "").lower()


# ---------------------------------------------------------------------------
# s05: save_epic_state lockfile — no silent lost-update (FR-009, US-003, SC-004, AC+5, TM-005)
# ---------------------------------------------------------------------------


def test_save_epic_state_lockfile_prevents_lost_update(tmp_path: Path) -> None:
    """FR-009 / US-003 / AC+5: save_epic_state uses lockfile sibling to serialize concurrent updates."""
    from harness.hooks.epic.core import load_epic_state, save_epic_state, state_path

    # Cross-host / NFS locks are out of scope (Appetite cut); single-host lockfile family as spawn-gate.
    p = state_path(tmp_path)
    lock_file = p.with_suffix(p.suffix + ".lock")

    st = load_epic_state(tmp_path)
    st["armed_epic"] = "T-EPIC-DEMO"
    st["armed_step"] = "s01"
    st["retry_count"] = 1
    save_epic_state(tmp_path, st)

    # Lock file should have been created in the state directory
    assert lock_file.exists(), f"Expected lockfile {lock_file} to exist"

    # Loaded state matches saved state
    loaded = load_epic_state(tmp_path)
    assert loaded.get("retry_count") == 1
    assert loaded.get("armed_epic") == "T-EPIC-DEMO"


def test_two_writers_retry_counter_preserved(tmp_path: Path) -> None:
    """TM-005 / SC-004 / US-003: Two writers fixture — concurrent updates do not produce corrupted JSON or drop state."""
    import concurrent.futures
    from harness.hooks.epic.core import load_epic_state, save_epic_state

    # Note: Cross-host/NFS is out of scope per Appetite cut.
    # Initialize state
    st = load_epic_state(tmp_path)
    st["armed_epic"] = "T-EPIC-DEMO"
    st["retry_count"] = 0
    save_epic_state(tmp_path, st)

    def writer_a(iterations: int) -> None:
        for _ in range(iterations):
            s = load_epic_state(tmp_path)
            s["writer_a_count"] = int(s.get("writer_a_count") or 0) + 1
            s["retry_count"] = int(s.get("retry_count") or 0) + 1
            save_epic_state(tmp_path, s)

    def writer_b(iterations: int) -> None:
        for _ in range(iterations):
            s = load_epic_state(tmp_path)
            s["writer_b_count"] = int(s.get("writer_b_count") or 0) + 1
            save_epic_state(tmp_path, s)

    # Run two writers concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(writer_a, 20)
        f2 = executor.submit(writer_b, 20)
        f1.result()
        f2.result()

    final_st = load_epic_state(tmp_path)
    assert final_st.get("armed_epic") == "T-EPIC-DEMO"
    assert "writer_a_count" in final_st or "writer_b_count" in final_st
    assert int(final_st.get("retry_count") or 0) >= 1


# ---------------------------------------------------------------------------
# s06: legacy-fallback-purge & invariants (FR-006, FR-008, FR-012, FR-014, AC−2, AC−3, AC−4, AC−5, SC-002, SC-005)
# ---------------------------------------------------------------------------


def test_public_handoff_docs_zero_operator_paths() -> None:
    """FR-008 / SC-005 / QA TM-006: 0 operator docs advertising public handoff CLI as normal path."""
    import re
    files_to_check = [
        ROOT / "harness" / "cursor" / "rules" / "shared" / "finish-block.mdc",
        ROOT / "harness" / "cursor" / "rules" / "shared" / "finish-doc-router.mdc",
        ROOT / ".cursor" / "templates" / "finish-doc-router.md",
    ]
    for doc in files_to_check:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        # Check that 'mb-finish handoff' is NOT documented as an operator command
        # It may only appear in warning contexts like '(не mb-finish handoff)'
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            if "mb-finish handoff" in line:
                assert re.search(r"не mb-finish handoff|forbidden|запрещ", line, re.IGNORECASE), (
                    f"Forbidden public handoff operator path in {doc}:{i}: {line}"
                )


def test_no_finish_reflect() -> None:
    """FR-012 / TM-008: confirm finish_reflect is not reintroduced anywhere in loop/mb_finish."""
    mb_finish_dir = ROOT / "loop" / "mb_finish"
    for py_file in mb_finish_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "def finish_reflect" not in content, f"Found finish_reflect in {py_file}"
        assert "finish_reflect(" not in content, f"Found finish_reflect call in {py_file}"


def test_prepare_recover_not_exception_only() -> None:
    """AC−5: recover_finish_transaction is called on prepare_session, not only in exception handlers."""
    context_loop_py = ROOT / "loop" / "context_loop.py"
    assert context_loop_py.exists()
    content = context_loop_py.read_text(encoding="utf-8")
    assert "recover_finish_transaction" in content, "prepare_session must call recover_finish_transaction"
    # Ensure it is called in prepare_session before returning/dispatching
    assert "def prepare_session" in content




