from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from loop.runtime_adapters import subagent_lifecycle as lifecycle


def _message(agent: str = "verify-qa", verdict: str = "PASS") -> str:
    return (
        "```json\n"
        + json.dumps(
            {
                "schema": "loop-gate-verdict/v1",
                "agent_id": agent,
                "verdict": verdict,
                "step_id": "QA",
                "session_id": "root-session",
                "epic_id": "T-HUB-001",
                "recorded_at": "2026-09-09T00:00:00Z",
            }
        )
        + "\n```"
    )


def test_codex_adapter_uses_shared_spawn_wait_lifecycle(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_hook(name, payload, *, cwd, runtime_id):
        calls.append((name, payload))
        return 0, ""

    monkeypatch.setattr(lifecycle, "_run_hook", fake_hook)
    monkeypatch.setattr(
        lifecycle,
        "gate_atomic_finish",
        lambda *args, **kwargs: {"ok": True, "epic_done": True},
    )

    adapter = lifecycle.SubagentLifecycle(tmp_path, "root-session", "codex")
    adapter.process_item(
        {
            "id": "spawn-qa",
            "tool": "spawn_agent",
            "prompt": "BACK QA review",
            "receiver_thread_ids": ["child-qa"],
        }
    )
    actions = adapter.process_item(
        {
            "id": "wait-qa",
            "tool": "wait",
            "agents_states": {
                "child-qa": {
                    "status": "completed",
                    "message": _message(),
                }
            },
        }
    )

    assert len(actions) == 1
    assert actions[0].agent_type == "verify-qa"
    assert actions[0].verdict == "PASS"
    assert [name for name, _ in calls] == ["subagent-start.py", "subagent-stop.py"]
    assert calls[1][1]["runtime_id"] == "codex"
    assert calls[1][1]["verdict"] == "PASS"
    assert actions[0].finish == {"ok": True, "epic_done": True}


def test_infer_agent_type_ignores_role_back() -> None:
    assert (
        lifecycle.infer_agent_type(
            "role: BACK\nmode: IMPLEMENT\nagent_type: verify-implement\n"
        )
        == "verify-implement"
    )
    assert lifecycle.infer_agent_type("role: BACK\nBACK QA review") == "verify-qa"
    assert lifecycle.infer_agent_type("role: BACK\nmode: IMPLEMENT\n") is None


def test_shared_lifecycle_does_not_replay_same_wait_completion(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        lifecycle,
        "_run_hook",
        lambda name, payload, *, cwd, runtime_id: (calls.append(name) or 0, ""),
    )
    monkeypatch.setattr(lifecycle, "gate_atomic_finish", lambda *args, **kwargs: None)
    adapter = lifecycle.SubagentLifecycle(tmp_path, "root-session", "codex")
    adapter.process_item(
        {"tool": "spawn_agent", "id": "spawn", "receiver_thread_ids": ["child"]}
    )
    wait = {
        "id": "wait",
        "tool": "wait",
        "agents_states": {"child": {"status": "completed", "message": _message()}},
    }
    assert len(adapter.process_item(wait)) == 1
    assert adapter.process_item(wait) == []
    assert calls == ["subagent-start.py", "subagent-stop.py"]

def test_infer_agent_type_from_blockers_pack_and_qa_review() -> None:
    blockers = (
        "BLOCKERS:\n"
        "1. x\n\n"
        "ALLOW WRITE:\n"
        "- a.py\n\n"
        "VERIFY:\n"
        "- bin/pytest a.py -q\n"
    )
    assert lifecycle.infer_agent_type(blockers) == "gate-repair"
    assert lifecycle.infer_agent_type("QA review for epic T-DEMO") == "verify-qa"



def test_shared_lifecycle_deduplicates_by_verifier_identity(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        lifecycle,
        "_run_hook",
        lambda name, payload, *, cwd, runtime_id: (calls.append(name) or 0, ""),
    )
    monkeypatch.setattr(lifecycle, "gate_atomic_finish", lambda *args, **kwargs: None)
    adapter = lifecycle.SubagentLifecycle(tmp_path, "root-session", "codex")

    # 1. Spawn 8 threads for identical verifier request
    adapter.process_item(
        {
            "tool": "spawn_agent",
            "id": "spawn-all",
            "prompt": "BACK QA review",
            "receiver_thread_ids": [f"child-{i}" for i in range(8)],
        }
    )

    # 2. Wait event returning 8 completed threads with same verifier identity verdict
    states = {
        f"child-{i}": {"status": "completed", "message": _message()}
        for i in range(8)
    }
    actions = adapter.process_item(
        {
            "id": "wait-all",
            "tool": "wait",
            "agents_states": states,
        }
    )

    # Exactly 1 action produced and 1 start/stop hook cycle executed
    assert len(actions) == 1
    assert actions[0].agent_type == "verify-qa"
    assert actions[0].verdict == "PASS"
    assert calls == ["subagent-start.py", "subagent-stop.py"]

    # 3. Subsequent wait on separate wait_id and thread for same verifier is also deduplicated
    adapter.process_item(
        {
            "tool": "spawn_agent",
            "id": "spawn-extra",
            "prompt": "BACK QA review",
            "receiver_thread_ids": ["child-extra"],
        }
    )
    extra_actions = adapter.process_item(
        {
            "id": "wait-extra",
            "tool": "wait",
            "agents_states": {"child-extra": {"status": "completed", "message": _message()}},
        }
    )
    assert extra_actions == []
    assert calls == ["subagent-start.py", "subagent-stop.py"]


def test_shared_lifecycle_process_item_is_thread_safe(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        lifecycle,
        "_run_hook",
        lambda name, payload, *, cwd, runtime_id: (calls.append(name) or 0, ""),
    )
    monkeypatch.setattr(lifecycle, "gate_atomic_finish", lambda *args, **kwargs: None)
    adapter = lifecycle.SubagentLifecycle(tmp_path, "root-session", "codex")
    adapter.process_item(
        {
            "tool": "spawn_agent",
            "id": "spawn",
            "prompt": "BACK QA review",
            "receiver_thread_ids": ["child"],
        }
    )
    wait = {
        "id": "wait",
        "tool": "wait",
        "agents_states": {"child": {"status": "completed", "message": _message()}},
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: adapter.process_item(wait), range(8)))

    assert sum(len(result) for result in results) == 1
    assert calls == ["subagent-start.py", "subagent-stop.py"]


def test_gate_atomic_finish_implement_pass_calls_finish(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class _Res:
        def model_dump(self):
            return {"ok": True, "finished_step": "s01"}

    def fake_finish(req):
        calls.append(req.step_id)
        return _Res()

    monkeypatch.setattr(
        "loop.mb_finish.finish_implement.finish_implement_step",
        fake_finish,
    )

    from harness.hooks.epic.core import default_state, save_epic_state

    st = default_state()
    st.update(
        {
            "active": True,
            "armed_step": "s01",
            "armed_epic": "T-HUB-TEST",
            "phase_run_id": "run-1",
            "last_verify_verdict": "PASS",
        }
    )
    save_epic_state(tmp_path, st)

    out = lifecycle.gate_atomic_finish(
        tmp_path,
        agent_type="verify-implement",
        verdict="PASS",
        session_id="sess",
    )
    assert out == {"ok": True, "finished_step": "s01"}
    assert calls == ["s01"]

    # idempotent when last_finish_tool already recorded for same phase_run
    st = default_state()
    st.update(
        {
            "active": True,
            "armed_step": "s02",
            "phase_run_id": "run-1",
            "last_verify_verdict": "PASS",
            "last_finish_tool": {
                "name": "mb-finish implement",
                "step_id": "s01",
                "phase_run_id": "run-1",
            },
        }
    )
    save_epic_state(tmp_path, st)
    out2 = lifecycle.gate_atomic_finish(
        tmp_path,
        agent_type="verify-implement",
        verdict="PASS",
        session_id="sess",
    )
    assert out2 == {"ok": True, "already_finished": True}
    assert calls == ["s01"]


def test_gate_atomic_finish_implement_fail_verdict_skips() -> None:
    assert (
        lifecycle.gate_atomic_finish(
            ".",
            agent_type="verify-implement",
            verdict="FAIL",
            session_id="sess",
        )
        is None
    )


def test_gate_atomic_finish_implement_missing_verify(monkeypatch, tmp_path) -> None:
    from harness.hooks.epic.core import default_state, save_epic_state

    st = default_state()
    st.update({"active": True, "armed_step": "s01", "last_verify_verdict": None})
    save_epic_state(tmp_path, st)
    out = lifecycle.gate_atomic_finish(
        tmp_path,
        agent_type="verify-implement",
        verdict="PASS",
        session_id="sess",
    )
    assert out is not None
    assert out["ok"] is False
    assert "verify_pass_missing" in out["diagnostic_codes"]


def test_gate_atomic_finish_analyze_pass_calls_finish(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    class _Res:
        def model_dump(self):
            return {"ok": True, "finished_step": "ANALYZE"}

    def fake_finish(req):
        calls.append(req.step_id)
        return _Res()

    monkeypatch.setattr("loop.mb_finish.impl.finish_analyze", fake_finish)

    from harness.hooks.epic.core import default_state, save_epic_state

    st = default_state()
    st.update(
        {
            "active": True,
            "armed_step": "ANALYZE",
            "phase": "ANALYZE",
            "armed_epic": "T-HUB-TEST",
            "phase_run_id": "run-analyze",
            "last_verify_verdict": "PASS",
        }
    )
    save_epic_state(tmp_path, st)

    out = lifecycle.gate_atomic_finish(
        tmp_path,
        agent_type="analyze-verify",
        verdict="PASS",
        session_id="sess",
    )
    assert out == {"ok": True, "finished_step": "ANALYZE"}
    assert calls == ["ANALYZE"]

    st = default_state()
    st.update(
        {
            "active": True,
            "armed_step": "ANALYZE",
            "phase": "ANALYZE",
            "phase_run_id": "run-analyze",
            "last_verify_verdict": "PASS",
            "last_finish_tool": {
                "name": "mb-finish analyze",
                "step_id": "ANALYZE",
                "phase_run_id": "run-analyze",
            },
        }
    )
    save_epic_state(tmp_path, st)
    out2 = lifecycle.gate_atomic_finish(
        tmp_path,
        agent_type="analyze-verify",
        verdict="PASS",
        session_id="sess",
    )
    assert out2 == {"ok": True, "already_finished": True}
    assert calls == ["ANALYZE"]


def test_gate_atomic_finish_analyze_wrong_phase_skips(tmp_path) -> None:
    from harness.hooks.epic.core import default_state, save_epic_state

    st = default_state()
    st.update(
        {
            "active": True,
            "armed_step": "s01",
            "phase": "IMPLEMENT",
            "last_verify_verdict": "PASS",
        }
    )
    save_epic_state(tmp_path, st)
    assert (
        lifecycle.gate_atomic_finish(
            tmp_path,
            agent_type="analyze-verify",
            verdict="PASS",
            session_id="sess",
        )
        is None
    )


def test_gate_atomic_finish_audit_has_no_verify_trigger() -> None:
    """AUDIT has verify_agent=null — no subagent PASS → atomic finish path."""
    assert (
        lifecycle.gate_atomic_finish(
            ".",
            agent_type="audit",
            verdict="PASS",
            session_id="sess",
        )
        is None
    )
