from loop.session_finalize import should_probe_analyze_promotion

def test_skip():
    assert should_probe_analyze_promotion(armed_step="ANALYZE", active_mode="ANALYZE") is False
    assert should_probe_analyze_promotion(armed_step="DECOMPOSE", active_mode="DECOMPOSE") is True


def test_resolve_close():
    from loop.session_finalize import freeze_session_start_identity, resolve_session_close_identity
    state = {"armed_epic": "E1", "armed_step": "ANALYZE", "armed_after_finish": "ANALYZE", "role": "back", "session_id": "s", "phase_run_id": "r"}
    freeze_session_start_identity(state, phase="DECOMPOSE", step_id="DECOMPOSE", session_id="s", phase_run_id="r")
    state["armed_step"] = "ANALYZE"
    close = resolve_session_close_identity(state)
    assert close.record_step_id == "DECOMPOSE"
    assert close.resume_from == "ANALYZE"


def test_promote_stale_receipt_after_decompose(tmp_path):
    from epic.core import save_epic_state
    from loop.epic_transition import promote_if_ready
    from loop.tests.test_epic_transition import _seed_decompose_index

    epic = "T-TEST-STALE-ANALYZE"
    decomp = _seed_decompose_index(tmp_path, epic)
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "ANALYZE",
            "last_finished_step": "DECOMPOSE",
            "armed_after_finish": "ANALYZE",
            "role": "BACK",
            "last_verify_evidence": {
                "schema": "loop-verifier-receipt/v1",
                "epic_id": "T-HUB-079-other",
                "step": "BUGFIX",
                "verdict": "PASS",
            },
        },
    )
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: ANALYZE\n"
        f"epic_id: {epic}\nstep_id: ANALYZE\n---\n",
        encoding="utf-8",
    )
    assert promote_if_ready(tmp_path, epic, "back") is None


def _load_ctx(name: str):
    import importlib.util
    import sys
    from pathlib import Path as P
    root = P(__file__).resolve().parents[2]
    path = root / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location(name, path)
    ctx = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    hooks = str(root / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(ctx)
    return ctx


def test_check_after_continues_on_analyze_after_decompose(tmp_path, monkeypatch):
    import pytest
    ctx = _load_ctx("context_loop_sf_check")
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    from epic.core import save_epic_state
    from loop.tests.test_epic_transition import _seed_decompose_index

    epic = "T-TEST-CHECK-AFTER-ANALYZE"
    decomp = _seed_decompose_index(tmp_path, epic)
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: ANALYZE\n"
        f"epic_id: {epic}\n"
        "step_id: ANALYZE\n"
        "---\n\n"
        "## load_now\n"
        f"1. [{decomp}/index.yaml]({decomp}/index.yaml)\n\n"
        "## Handoff ANALYZE\n"
        f"- epic: {epic}\n",
        encoding="utf-8",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": epic,
            "armed_decompose": f"{decomp}/index.yaml",
            "armed_step": "ANALYZE",
            "last_finished_step": "DECOMPOSE",
            "armed_after_finish": "ANALYZE",
            "role": "back",
            "active": True,
            "status": "armed",
            "pending_fingerprint_before": "deadbeef",
            "last_verify_evidence": {
                "schema": "loop-verifier-receipt/v1",
                "epic_id": "T-HUB-079-other",
                "step": "BUGFIX",
                "verdict": "PASS",
            },
        },
    )
    out = ctx.check_after(tmp_path, fingerprint_before="different")
    assert out.get("halt") is not True, out
    assert out.get("diagnostic_code") != "verdict_wrong_step"
    assert out.get("ok") is True, out


def test_record_abort_keeps_frozen_decompose_identity(tmp_path, monkeypatch):
    import json
    ctx = _load_ctx("context_loop_sf_record")
    monkeypatch.setenv("DEV_HUB", str(tmp_path / "hub"))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    from epic.core import save_epic_state
    from harness.hooks.session_resilience import load_last_session
    from loop.session_finalize import freeze_session_start_identity

    epic = "T-HUB-080-x"
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: ANALYZE\n"
        f"epic_id: {epic}\nstep_id: ANALYZE\n---\n\n## load_now\n1. x\n",
        encoding="utf-8",
    )
    state = {
        "armed_epic": epic,
        "armed_step": "ANALYZE",
        "armed_after_finish": "ANALYZE",
        "last_finished_step": "DECOMPOSE",
        "phase": "ANALYZE",
        "role": "back",
        "session_id": "sess-freeze-1",
        "phase_run_id": "run-freeze-1",
        "active": True,
        "status": "running",
        "runtime": "codex",
        "last_finish_tool": {
            "name": "mb-finish decompose",
            "step_id": "DECOMPOSE",
            "session_id": "sess-freeze-1",
            "epic_id": epic,
            "fingerprint": "abc",
        },
    }
    freeze_session_start_identity(
        state,
        phase="DECOMPOSE",
        step_id="DECOMPOSE",
        session_id="sess-freeze-1",
        phase_run_id="run-freeze-1",
    )
    save_epic_state(tmp_path, state)
    log = tmp_path / "session.log"
    log.write_text(
        json.dumps({"type": "thread.started", "thread_id": "t1"})
        + "\n"
        + json.dumps({"type": "turn.completed", "usage": {}})
        + "\n"
        + "SESSION_END session=1 exit_code=0\n",
        encoding="utf-8",
    )
    out = ctx.record_abort(tmp_path, log_path=log, exit_code=0, runtime="codex")
    assert out.get("ok") is True, out
    payload = load_last_session(tmp_path, track="epic")
    assert payload is not None
    assert payload["step_id"] == "DECOMPOSE"
    assert payload["phase"] == "DECOMPOSE"
    assert payload["resume_from"] == "ANALYZE"


def test_ownership_prefers_frozen_start_after_finish_advance():
    from loop.session_finalize import (
        apply_ownership_identity,
        freeze_session_start_identity,
        ownership_expected_step,
        resolve_session_close_identity,
    )

    state = {
        "armed_epic": "E1",
        "armed_step": "QA",
        "armed_after_finish": "QA",
        "role": "BACK",
        "session_id": "s",
        "phase_run_id": "r",
        "last_finished_step": "BUGFIX",
    }
    freeze_session_start_identity(
        state,
        phase="BACK BUGFIX",
        step_id="BUGFIX",
        session_id="s",
        phase_run_id="r",
    )
    assert ownership_expected_step(state) == "BUGFIX"
    identity = apply_ownership_identity(
        {"step": "QA", "epic_id": "E1", "session_id": "s"},
        state,
    )
    assert identity["step"] == "BUGFIX"
    close = resolve_session_close_identity(state)
    assert close.record_step_id == "BUGFIX"
    assert close.resume_from == "QA"


def test_ownership_without_freeze_follows_armed_step():
    from loop.session_finalize import ownership_expected_step

    assert ownership_expected_step({"armed_step": "s03"}) == "s03"
