from __future__ import annotations

import json
from pathlib import Path

from harness.hooks.epic.core import default_state, save_epic_state
from loop.gate_identity import GateIdentity
from loop.runtime_adapters.subagent_lifecycle import (
    PendingSubagent,
    SubagentLifecycle,
    rewrite_spawn_prompt,
)


def test_spawn_prompt_contains_gate_identity(tmp_path: Path) -> None:
    """FR-006, SC-004, US-004, TM-004, cp1: Codex spawn_agent prompt contains GATE_IDENTITY header and frozen SoT."""
    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-codex-delivery-1"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": "T-HUB-DRIFT",  # drift ignored in favor of frozen SoT
            "armed_step": "s99",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-codex-001",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    lifecycle = SubagentLifecycle(tmp_path, session_id, "codex")
    spawn_item = {
        "id": "spawn-call-1",
        "tool": "spawn_agent",
        "prompt": "agent_type: verify-bugfix\nCheck AC criteria.",
        "receiver_thread_ids": ["thread-codex-1"],
    }

    lifecycle.process_item(spawn_item)

    prompt = spawn_item.get("prompt", "")
    assert f"GATE_IDENTITY session_id={session_id} epic_id={epic} step_id=BUGFIX" in prompt
    assert "Fence MUST use these exact IDs for session_id, epic_id, and step_id." in prompt
    assert "agent_type: verify-bugfix" in prompt
    assert "Check AC criteria." in prompt

    # Ensure idempotency: re-running rewrite on already injected prompt does not duplicate header
    sot = lifecycle.get_gate_identity()
    re_rewritten = rewrite_spawn_prompt(prompt, sot)
    assert re_rewritten == prompt
    assert prompt.count("GATE_IDENTITY") == 1


def test_pending_thread_bound_to_sot(tmp_path: Path) -> None:
    """FR-006, cp2: Pending thread is bound to frozen GateIdentity on spawn observe."""
    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-codex-delivery-2"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "armed_epic": epic,
            "armed_step": "s04",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK IMPLEMENT",
                "step_id": "s04",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-codex-002",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    lifecycle = SubagentLifecycle(tmp_path, session_id, "codex")
    spawn_item = {
        "id": "spawn-call-2",
        "tool": "spawn_agent",
        "prompt": "agent_type: verify-implement\nVerify s04 AC.",
        "receiver_thread_ids": ["thread-a", "thread-b"],
    }

    lifecycle.process_item(spawn_item)

    # Both threads must be bound to frozen SoT
    assert "thread-a" in lifecycle.pending_threads
    assert "thread-b" in lifecycle.pending_threads

    pending_a = lifecycle.pending_threads["thread-a"]
    assert isinstance(pending_a, PendingSubagent)
    assert pending_a.agent_type == "verify-implement"
    assert pending_a.spawn_tool_use_id == "spawn-call-2"
    assert pending_a.identity is not None
    assert pending_a.identity.session_id == session_id
    assert pending_a.identity.epic_id == epic
    assert pending_a.identity.step_id == "s04"

    ident_a = lifecycle.get_pending_identity("thread-a")
    assert ident_a == pending_a.identity

    pending_b = lifecycle.pending_threads["thread-b"]
    assert pending_b.identity == pending_a.identity


def test_rewrite_spawn_prompt_standalone() -> None:
    """Unit test for rewrite_spawn_prompt with GateIdentity object or None."""
    sot = GateIdentity(
        session_id="s1",
        epic_id="e1",
        step_id="BUGFIX",
    )
    raw = "agent_type: verify-bugfix"
    rewritten = rewrite_spawn_prompt(raw, sot)
    assert "GATE_IDENTITY session_id=s1 epic_id=e1 step_id=BUGFIX" in rewritten
    assert "agent_type: verify-bugfix" in rewritten

    # None identity returns raw
    assert rewrite_spawn_prompt(raw, None) == raw
    assert rewrite_spawn_prompt(None, None) == ""


def test_spawn_validate_injects_gate_identity_before_child(tmp_path: Path) -> None:
    """Real pre-delivery path: spawn_validate mutates prompt for PreToolUse updatedInput."""
    import sys

    hooks = Path(__file__).resolve().parents[2] / "harness" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    from spawn_validate import ensure_gate_identity_prompt, validate_spawn_input

    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "verify-bugfix.md").write_text(
        "---\nname: verify-bugfix\noverlay:\n  managed: true\n  mode: gate\n"
        "  default_loop: true\n  requires_model: true\n  verdict: pass-fail\n---\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_BUGFIX_MODEL=sonnet\n", encoding="utf-8"
    )
    bugfix = tmp_path / "memory-bank/back/bugfix/T-HUB-091/bugfix-20260910-x.md"
    bugfix.parent.mkdir(parents=True)
    bugfix.write_text("# bf\n## Changes Implemented\n- a\n## Verification\n- ok\n", encoding="utf-8")
    queue = tmp_path / "memory-bank/back/bugfix/T-HUB-091/bugfix-queue.yaml"
    queue.write_text("schema: epic-bugfix-queue/v1\nepic_id: T-HUB-091-gate-identity-sot-consolidation\n", encoding="utf-8")

    state = {
        "session_id": "sess-codex-delivery-1",
        "gate_identity": {
            "session_id": "sess-codex-delivery-1",
            "epic_id": "T-HUB-091-gate-identity-sot-consolidation",
            "step_id": "BUGFIX",
        },
    }
    tool_input = {
        "subagent_type": "verify-bugfix",
        "prompt": f"agent_type: verify-bugfix\nALLOW READ\n{queue.relative_to(tmp_path)}\n{bugfix.relative_to(tmp_path)}\n",
    }
    import os

    os.environ["EPIC_LOOP"] = "1"
    deny, _ = validate_spawn_input(tool_input, state, tmp_path)
    assert deny == []
    assert (
        "GATE_IDENTITY session_id=sess-codex-delivery-1 "
        "epic_id=T-HUB-091-gate-identity-sot-consolidation step_id=BUGFIX"
        in tool_input["prompt"]
    )
    # idempotent helper
    again = dict(tool_input)
    assert ensure_gate_identity_prompt(
        again, state, agent_type="verify-bugfix", cwd=tmp_path
    ) == []
    assert again["prompt"].count("GATE_IDENTITY session_id=") == 1


def test_post_wait_start_is_mark_only(tmp_path: Path, monkeypatch) -> None:
    """FR-010: Post-wait SubagentStart call is mark-only, does not act as delivery channel."""
    epic = "T-HUB-091-gate-identity-sot-consolidation"
    session_id = "sess-codex-delivery-3"
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK BUGFIX",
            "mode": "bugfix",
            "armed_epic": epic,
            "armed_step": "BUGFIX",
            "session_id": session_id,
            "session_start_identity": {
                "schema": "loop-session-start-identity/v1",
                "phase": "BACK BUGFIX",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "role": "BACK",
                "phase_run_id": "run-codex-003",
                "session_id": session_id,
            },
        }
    )
    save_epic_state(tmp_path, st)

    hook_calls: list[tuple[str, dict]] = []

    def fake_run_hook(name, payload, *, cwd, runtime_id, session_id=None):
        hook_calls.append((name, payload))
        return 0, ""

    monkeypatch.setattr("loop.runtime_adapters.subagent_lifecycle._run_hook", fake_run_hook)
    monkeypatch.setattr(
        "loop.runtime_adapters.subagent_lifecycle.gate_atomic_finish",
        lambda *args, **kwargs: {"ok": True},
    )

    lifecycle = SubagentLifecycle(tmp_path, session_id, "codex")
    lifecycle.process_item(
        {
            "id": "spawn-call-3",
            "tool": "spawn_agent",
            "prompt": "agent_type: verify-bugfix",
            "receiver_thread_ids": ["thread-postwait"],
        }
    )

    fence_message = (
        "```json\n"
        + json.dumps(
            {
                "schema": "loop-gate-verdict/v1",
                "agent_id": "verify-bugfix",
                "verdict": "PASS",
                "step_id": "BUGFIX",
                "epic_id": epic,
                "session_id": session_id,
                "recorded_at": "2026-09-10T12:00:00Z",
            }
        )
        + "\n```"
    )

    actions = lifecycle.process_item(
        {
            "id": "wait-call-3",
            "tool": "wait",
            "agents_states": {
                "thread-postwait": {
                    "status": "completed",
                    "message": fence_message,
                }
            },
        }
    )

    assert len(actions) == 1
    assert actions[0].verdict == "PASS"
    assert [name for name, _ in hook_calls] == ["subagent-start.py", "subagent-stop.py"]
    # Thread was removed from pending after wait completion
    assert "thread-postwait" not in lifecycle.pending_threads
