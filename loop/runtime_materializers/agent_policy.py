from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
import yaml

from loop.runtime_materializers.codex_agent_toml import (
    CodexAgentTomlError,
    split_markdown_frontmatter,
)


class AgentPolicyError(ValueError):
    pass


class UnsupportedRuntimePolicyError(AgentPolicyError):
    pass


class PolicyFieldMapping(BaseModel):
    support: Literal["native", "hook", "unsupported"]
    target: str | None = None
    notes: str = ""


class CodexPolicyMapping(BaseModel):
    schema_version: str = "codex-policy-mapping/v1"
    description: str = ""
    fields: dict[str, PolicyFieldMapping] = Field(default_factory=dict)


def load_codex_policy_mapping(
    mapping_path: str | Path | None = None,
) -> CodexPolicyMapping:
    if mapping_path is None:
        path = Path(__file__).parent / "codex_policy_mapping.yaml"
    else:
        path = Path(mapping_path)
    if not path.is_file():
        raise AgentPolicyError(f"Codex policy mapping file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CodexPolicyMapping(**data)


class PolicyRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    disallowedTools: list[str] = Field(default_factory=list)
    maxTurns: int | None = None
    overlay: dict[str, Any] | str | None = None
    managed: bool = False
    mode: str | None = None
    verdict: str | None = None
    allow_worktree: bool | None = None
    requires_model: bool | str | None = None
    default_loop: bool | None = None
    default_chat: bool | None = None
    color: str | None = None
    source_sha256: str | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)

    def policy_fingerprint(self) -> str:
        data = {
            "name": self.name,
            "description": self.description,
            "tools": sorted(self.tools),
            "disallowedTools": sorted(self.disallowedTools),
            "maxTurns": self.maxTurns,
            "overlay": self.overlay,
            "managed": self.managed,
            "mode": self.mode,
            "verdict": self.verdict,
            "allow_worktree": self.allow_worktree,
            "requires_model": self.requires_model,
            "default_loop": self.default_loop,
            "default_chat": self.default_chat,
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def validate_codex_runtime_support(
        self,
        mapping: CodexPolicyMapping | None = None,
    ) -> None:
        if mapping is None:
            mapping = load_codex_policy_mapping()

        if self.disallowedTools:
            deny_mapping = mapping.fields.get("disallowedTools")
            if not deny_mapping or deny_mapping.support == "unsupported":
                raise UnsupportedRuntimePolicyError(
                    f"Agent {self.name} requires disallowedTools {self.disallowedTools} "
                    "which is unsupported in Codex runtime without a hook row (unsupported_runtime_policy)"
                )



def _split_csv_or_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [part.strip() for part in val.split(",") if part.strip()]
    return []


def parse_agent_policy_text(
    src_text: str,
    *,
    fallback_name: str,
    fallback_description: str = "",
) -> PolicyRecord:
    meta, _body = split_markdown_frontmatter(src_text)
    meta_copy = dict(meta)

    # Flatten overlay if dict
    overlay = meta_copy.get("overlay")
    if isinstance(overlay, dict):
        for k, v in overlay.items():
            if k not in meta_copy:
                meta_copy[k] = v

    # Normalize tools and disallowedTools
    if "tools" in meta_copy:
        meta_copy["tools"] = _split_csv_or_list(meta_copy["tools"])
    if "disallowedTools" in meta_copy:
        meta_copy["disallowedTools"] = _split_csv_or_list(meta_copy["disallowedTools"])

    # Known FR-001 fields
    known_fields = {
        "name",
        "description",
        "tools",
        "disallowedTools",
        "maxTurns",
        "overlay",
        "managed",
        "mode",
        "verdict",
        "allow_worktree",
        "requires_model",
        "default_loop",
        "default_chat",
        "color",
        "source_sha256",
    }

    unknown_keys = [k for k in meta_copy if k not in known_fields]
    is_managed = bool(meta_copy.get("managed", False))

    if is_managed and unknown_keys:
        raise AgentPolicyError(
            f"Managed agent frontmatter contains unknown/unsupported extra keys: {sorted(unknown_keys)} (Failure TM-005)"
        )

    if "name" not in meta_copy or not meta_copy["name"]:
        meta_copy["name"] = fallback_name
    if "description" not in meta_copy or not meta_copy["description"]:
        meta_copy["description"] = fallback_description

    extras = {k: meta_copy[k] for k in unknown_keys}
    if "source_sha256" not in meta_copy or not meta_copy["source_sha256"]:
        meta_copy["source_sha256"] = hashlib.sha256(src_text.encode("utf-8")).hexdigest()

    try:
        record = PolicyRecord(**meta_copy)
        record.extra_fields = extras
        return record
    except Exception as err:
        raise AgentPolicyError(f"Failed to validate PolicyRecord: {err}") from err


def parse_agent_policy(file_path: str | Path) -> PolicyRecord:
    path = Path(file_path)
    if not path.is_file():
        raise AgentPolicyError(f"Agent policy file not found: {path}")
    text = path.read_text(encoding="utf-8")
    fallback_name = path.stem
    return parse_agent_policy_text(text, fallback_name=fallback_name)


def get_always_inject_set(
    agents_dir: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> frozenset[str]:
    """Derive always inject set from PolicyRecord.managed/verdict ∪ manifest/phase registry.

    Includes all finish/managed agents (software+video+repair+sunset) plus base aliases.
    """
    root_path = Path(__file__).resolve().parents[2]
    if agents_dir is None:
        agents_dir = root_path / "harness" / "agents"
    if manifest_path is None:
        manifest_path = root_path / "harness" / "manifest.yaml"

    inject_set: set[str] = {"verify", "reviewer"}

    # 1. Inspect agent md policies
    agents_path = Path(agents_dir)
    if agents_path.is_dir():
        for p in agents_path.glob("*.md"):
            try:
                rec = parse_agent_policy(p)
                if rec.managed or rec.verdict != "none" or rec.mode in {"gate", "repair"}:
                    inject_set.add(rec.name)
            except Exception:
                continue

    # 2. Inspect manifest
    mf_path = Path(manifest_path)
    if mf_path.is_file():
        try:
            m_data = yaml.safe_load(mf_path.read_text(encoding="utf-8")) or {}
            for agent_name in m_data.get("agents", {}).keys():
                inject_set.add(agent_name)
        except Exception:
            pass

    return frozenset(inject_set)

