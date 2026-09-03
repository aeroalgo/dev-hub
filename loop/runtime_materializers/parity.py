from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from loop.runtime_materializers.hooks_json import CODEX_MIN_VERSION
from loop.runtime_materializers.manifest_schema import HarnessManifest, load_manifest

REQUIRED_CODEX_EVENTS: frozenset[str] = frozenset(
    {
        "Stop",
        "SubagentStop",
        "PreToolUse",
        "PostToolUse",
        "UserPromptSubmit",
        "SessionStart",
        "SubagentStart",
    }
)

REQUIRED_CODEX_AGENTS: frozenset[str] = frozenset(
    {
        "verify-implement",
        "gate-repair",
        "verify-bugfix",
        "verify-decompose",
        "verify-qa",
        "analyze-verify",
        "sunset-inventory",
    }
)


def check_codex_parity(
    hooks_json_path: str | Path,
    manifest_path: str | Path | None = None,
) -> list[str]:
    hooks_path = Path(hooks_json_path)
    issues: list[str] = []

    if not hooks_path.exists():
        return [f"missing_hooks_json: {hooks_path}"]

    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"invalid_json: {e}"]

    hooks = data.get("hooks", {})
    existing_events = set(hooks.keys())

    missing_events = sorted(REQUIRED_CODEX_EVENTS - existing_events)
    for ev in missing_events:
        issues.append(f"missing_required_event: {ev}")

    # Check agents parity if manifest is provided
    if manifest_path is not None:
        man_path = Path(manifest_path)
        if man_path.exists():
            manifest = load_manifest(man_path)
            claude_agents = {
                name for name, agent in manifest.agents.items()
                if "claude" in agent.runtimes
            }
            codex_agents = {
                name for name, agent in manifest.agents.items()
                if "codex" in agent.runtimes and agent.runtimes["codex"].get("materialize")
            }
            # Codex agents must cover Claude managed agents
            missing_agents = sorted(claude_agents - codex_agents)
            for ag in missing_agents:
                issues.append(f"missing_codex_agent: {ag}")

    return issues
