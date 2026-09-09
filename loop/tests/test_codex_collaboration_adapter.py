from __future__ import annotations

from loop.runtime_adapters.codex_collaboration import (
    normalize_collaboration_item,
    normalize_tool_identity,
)


def test_normalize_codex_collaboration_aliases() -> None:
    cases = {
        "multi_agent_v1_spawn_agent": ("multi_agent_v1", "spawn_agent"),
        "multi_agent_v1__wait_agent": ("multi_agent_v1", "wait_agent"),
        "collaboration_wait_agent_123": ("collaboration", "wait_agent"),
        "spawn_agent": ("multi_agent_v1", "spawn_agent"),
        "unrelated_tool": (None, "unrelated_tool"),
    }

    for raw, expected in cases.items():
        assert normalize_tool_identity(raw) == expected


def test_normalize_collaboration_item_preserves_payload() -> None:
    item = {
        "type": "collab_tool_call",
        "tool": "multi_agent_v1_spawn_agent",
        "prompt": "agent_type=verify-bugfix",
        "receiver_thread_ids": ["thread-1"],
    }

    normalized = normalize_collaboration_item(item)

    assert normalized == {
        **item,
        "tool": "spawn_agent",
        "namespace": "multi_agent_v1",
    }
    assert item["tool"] == "multi_agent_v1_spawn_agent"
