from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from loop.runtime_materializers.agent_policy import (
    AgentPolicyError,
    load_codex_policy_mapping,
    parse_agent_policy_text,
)
from loop.runtime_materializers.codex_agent_toml import markdown_agent_to_codex_toml
from loop.runtime_materializers.manifest_schema import HarnessManifest


class MaterializationError(Exception):
    pass


def materialize_agents(
    manifest: HarnessManifest,
    runtime: str,
    dest_root: Path,
    repo_root: Path | None = None,
) -> list[str]:
    """
    Materialize agent files from harness/agents/ according to manifest agents section.
    For agents where runtimes[runtime].type == 'materialize' or runtimes[runtime].materialize is True:
    copy source file to destination.
    """
    materialized: list[str] = []
    base_root = repo_root if repo_root is not None else dest_root

    codex_mapping = None
    if runtime == "codex":
        codex_mapping = load_codex_policy_mapping()

    for agent_name, agent_cfg in manifest.agents.items():
        rt_cfg = agent_cfg.runtimes.get(runtime)
        if not rt_cfg:
            continue

        # Check if type is materialize or materialize boolean field is True
        is_materialize = rt_cfg.get("type") == "materialize" or rt_cfg.get("materialize") is True
        if not is_materialize:
            continue

        src_path = Path(agent_cfg.source)
        if not src_path.is_absolute():
            src_path = base_root / src_path

        if not src_path.exists():
            raise MaterializationError(f"Missing agent source file for {agent_name}: {src_path}")

        target_rel = rt_cfg.get("target") or f".{runtime}/agents/{agent_name}.md"
        dest_path = dest_root / target_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if dest_path.suffix == ".toml":
            src_text = src_path.read_text(encoding="utf-8")
            try:
                policy_record = parse_agent_policy_text(
                    src_text,
                    fallback_name=agent_name,
                    fallback_description=str(agent_cfg.description or ""),
                )
                if codex_mapping:
                    policy_record.validate_codex_runtime_support(codex_mapping)
            except AgentPolicyError as err:
                raise MaterializationError(f"Agent policy validation failed for {agent_name}: {err}") from err

            policy_fingerprint = policy_record.policy_fingerprint()
            source_prompt_sha256 = hashlib.sha256(src_text.encode("utf-8")).hexdigest()

            dest_path.write_text(
                markdown_agent_to_codex_toml(
                    src_text,
                    fallback_name=agent_name,
                    fallback_description=str(agent_cfg.description or ""),
                    policy_fingerprint=policy_fingerprint,
                    source_prompt_sha256=source_prompt_sha256,
                ),
                encoding="utf-8",
            )

            # Write sidecar .codex/agents/<id>.policy.json
            sidecar_path = dest_path.with_name(f"{dest_path.stem}.policy.json")
            sidecar_data = {
                "name": policy_record.name,
                "policy_fingerprint": policy_fingerprint,
                "source_prompt_sha256": source_prompt_sha256,
                "disallowedTools": policy_record.disallowedTools,
                "tools": policy_record.tools,
                "managed": policy_record.managed,
            }
            sidecar_path.write_text(json.dumps(sidecar_data, indent=2) + "\n", encoding="utf-8")
            materialized.append(str(sidecar_path))
        else:
            shutil.copy2(src_path, dest_path)
        materialized.append(str(dest_path))

    return materialized
