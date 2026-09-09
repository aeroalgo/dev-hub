from __future__ import annotations

import json

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
        return 0

    monkeypatch.setattr(lifecycle, "_run_hook", fake_hook)
    monkeypatch.setattr(
        lifecycle,
        "auto_finish_after_gate",
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


def test_shared_lifecycle_does_not_replay_same_wait_completion(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        lifecycle,
        "_run_hook",
        lambda name, payload, *, cwd, runtime_id: calls.append(name) or 0,
    )
    monkeypatch.setattr(lifecycle, "auto_finish_after_gate", lambda *args, **kwargs: None)
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
