"""Codex collaboration transport normalization.

OmniRoute may serialize a namespaced Responses tool as a flat function name.
The loop keeps the canonical Codex tool identity at the adapter boundary so
post-session evidence and the native router use the same names.
"""

from __future__ import annotations

from typing import Any


COLLABORATION_NAMESPACES = ("multi_agent_v1", "multi_agent_v2", "collaboration")
DEFAULT_COLLABORATION_NAMESPACE = "multi_agent_v1"
COLLABORATION_TOOLS = frozenset(
    {
        "spawn_agent",
        "wait",
        "wait_agent",
        "send_input",
        "resume_agent",
        "close_agent",
        "send_message",
        "followup_task",
        "interrupt_agent",
        "list_agents",
    }
)


def normalize_tool_identity(
    name: str | None,
    namespace: str | None = None,
) -> tuple[str | None, str | None]:
    """Return ``(namespace, name)`` for a Codex collaboration tool.

    The function is deliberately conservative: unknown names and ambiguous
    flat names stay untouched and therefore fail closed in the native router.
    """
    if not isinstance(name, str) or not name.strip():
        return namespace or None, name

    raw_name = name.strip()
    raw_namespace = namespace.strip() if isinstance(namespace, str) else None
    if raw_namespace:
        return raw_namespace, raw_name

    for candidate_namespace in COLLABORATION_NAMESPACES:
        for separator in (".", "__", "_"):
            prefix = f"{candidate_namespace}{separator}"
            if not raw_name.startswith(prefix):
                continue
            candidate = raw_name[len(prefix) :]
            for tool in sorted(COLLABORATION_TOOLS, key=len, reverse=True):
                if candidate == tool or (
                    candidate.startswith(f"{tool}_")
                    and all(
                        char.isascii() and char.isalnum()
                        for char in candidate[len(tool) + 1 :]
                    )
                ):
                    return candidate_namespace, tool

    if raw_name in COLLABORATION_TOOLS:
        return DEFAULT_COLLABORATION_NAMESPACE, raw_name
    return None, raw_name


def normalize_collaboration_item(item: dict[str, Any]) -> dict[str, Any]:
    """Copy and normalize one Codex ``collab_tool_call`` log item."""
    normalized = dict(item)
    if normalized.get("type") != "collab_tool_call":
        return normalized
    namespace, name = normalize_tool_identity(
        normalized.get("tool"), normalized.get("namespace")
    )
    if name is not None:
        normalized["tool"] = name
    if namespace is not None:
        normalized["namespace"] = namespace
    return normalized
