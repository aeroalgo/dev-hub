from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from loop.runtime_materializers.hooks_json import (
    CODEX_MIN_VERSION,
    hooks_meta_path,
)
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

    # Check meta hash / drift if manifest is provided
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

            # Verify meta hash against manifest
            meta_path = hooks_meta_path(hooks_path)
            if not meta_path.exists():
                issues.append(f"missing_meta_file: {meta_path}")
            else:
                try:
                    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
                    manifest_hash = hashlib.sha256(man_path.read_bytes()).hexdigest()
                    if meta_data.get("manifest_hash") != manifest_hash:
                        issues.append(f"manifest_hash_mismatch: {meta_path}")
                except Exception as e:
                    issues.append(f"invalid_meta_json: {e}")

            # Check if hooks.json was hand-edited vs generated output
            expected_dict: dict[str, list[dict[str, object]]] = {}
            for hook_name, hook_def in manifest.hooks.items():
                codex_config = hook_def.runtimes.get("codex", {})
                if not codex_config.get("hooks_json_entry"):
                    continue
                from loop.runtime_materializers.hooks_json import EVENT_MAPPING
                ev_name = EVENT_MAPPING.get(hook_name, hook_name)
                entry = {
                    "type": "command",
                    "command": f"python3 {hook_def.source}",
                }
                if hook_name in ("agent-pretool", "agent-posttool", "agent-posttool-agent"):
                    entry["matcher"] = "Agent|Task"
                elif hook_name in ("bash-pretool", "bash-output-cap", "agent-posttool-bash"):
                    entry["matcher"] = "Bash"
                    if hook_name in ("bash-output-cap", "agent-posttool-bash"):
                        entry["timeout_ms"] = 45000
                if ev_name not in expected_dict:
                    expected_dict[ev_name] = []
                expected_dict[ev_name].append(entry)

            if data.get("hooks") != expected_dict:
                issues.append(f"hooks_content_mismatch: {hooks_path}")

    return issues
