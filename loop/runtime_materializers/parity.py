from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from loop.runtime_materializers.agent_policy import (
    AgentPolicyError,
    load_codex_policy_mapping,
    parse_agent_policy,
    parse_agent_policy_text,
)
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


def check_codex_parity(
    hooks_json_path: str | Path,
    manifest_path: str | Path | None = None,
    agents_dir: str | Path | None = None,
    root_dir: str | Path | None = None,
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

            # Check for orphan harness/agents/*.md files not declared in manifest (FR-004 / US-004)
            if agents_dir is not None:
                ad_path = Path(agents_dir)
            else:
                ad_path = man_path.parent / "agents"

            if ad_path.exists() and ad_path.is_dir():
                for prompt_file in sorted(ad_path.glob("*.md")):
                    agent_id = prompt_file.stem
                    if agent_id not in manifest.agents:
                        issues.append(f"missing_manifest_agent: {agent_id}")

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
                elif hook_name == "write-pretool":
                    entry["matcher"] = "Write|Edit|NotebookEdit"
                if ev_name not in expected_dict:
                    expected_dict[ev_name] = []
                expected_dict[ev_name].append(entry)

            if data.get("hooks") != expected_dict:
                issues.append(f"hooks_content_mismatch: {hooks_path}")

            # FR-005 / FR-013 / TM-001: Policy matrix validation and sidecar parity
            try:
                codex_mapping = load_codex_policy_mapping()
            except Exception as e:
                issues.append(f"unsupported_runtime_policy: failed to load mapping: {e}")
                codex_mapping = None

            base_root = Path(root_dir) if root_dir else (man_path.parent.parent if man_path.parent.name == "harness" else man_path.parent)

            if ad_path.exists() and ad_path.is_dir():
                for prompt_file in sorted(ad_path.glob("*.md")):
                    agent_id = prompt_file.stem
                    try:
                        policy_record = parse_agent_policy(prompt_file)
                        if codex_mapping:
                            policy_record.validate_codex_runtime_support(codex_mapping)
                    except AgentPolicyError as err:
                        err_str = str(err)
                        if "unsupported_runtime_policy" in err_str:
                            issues.append(f"unsupported_runtime_policy: {agent_id}: {err}")
                        else:
                            issues.append(f"codex_policy_dropped: {agent_id}: {err}")
                        continue

                    # If agent is in codex runtime, check sidecar and TOML fingerprint consistency
                    if agent_id in manifest.agents:
                        agent_cfg = manifest.agents[agent_id]
                        rt_cfg = agent_cfg.runtimes.get("codex", {})
                        is_materialize = rt_cfg.get("type") == "materialize" or rt_cfg.get("materialize") is True
                        if is_materialize:
                            target_rel = rt_cfg.get("target") or f".codex/agents/{agent_id}.toml"
                            dest_toml = base_root / target_rel
                            sidecar_path = dest_toml.with_name(f"{dest_toml.stem}.policy.json")
                            if not dest_toml.exists():
                                issues.append(f"missing_codex_agent: {dest_toml}")
                            else:
                                toml_content = dest_toml.read_text(encoding="utf-8")
                                expected_fp = policy_record.policy_fingerprint()
                                if f"# policy_fingerprint: {expected_fp}" not in toml_content:
                                    issues.append(f"codex_policy_dropped: {agent_id}: TOML missing policy_fingerprint")

                            if not sidecar_path.exists():
                                issues.append(f"codex_policy_dropped: {agent_id}: missing sidecar {sidecar_path}")
                            else:
                                try:
                                    sc_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
                                    sc_disallowed = sc_data.get("disallowedTools", [])
                                    if sorted(sc_disallowed) != sorted(policy_record.disallowedTools):
                                        issues.append(
                                            f"codex_policy_dropped: {agent_id}: disallowedTools mismatch in sidecar"
                                        )
                                    if sc_data.get("policy_fingerprint") != policy_record.policy_fingerprint():
                                        issues.append(
                                            f"codex_policy_dropped: {agent_id}: policy_fingerprint mismatch in sidecar"
                                        )
                                except Exception as err:
                                    issues.append(f"codex_policy_dropped: {agent_id}: invalid sidecar json: {err}")

    return issues
