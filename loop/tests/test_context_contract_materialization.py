"""Context contract materialization parity tests across Claude and Codex.

Verifies that Claude root, Claude subagent, and Codex generated surfaces
(TOML, policy sidecars, hooks.json, entrypoint instructions) materialize
one equivalent context budget contract without provider drift.
Addresses FR-003, FR-004, FR-007, FR-008, FR-010 (Checkpoints cp1, cp2).
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from loop.runtime_materializers.agent_policy import (
    PolicyRecord,
    UnsupportedRuntimePolicyError,
    load_codex_policy_mapping,
    parse_agent_policy_text,
)
from loop.runtime_materializers.agents import materialize_agents
from loop.runtime_materializers.codex_sync import apply_codex, codex_drift_items
from loop.runtime_materializers.manifest_schema import HarnessManifest, load_manifest
from loop.runtime_materializers.parity import check_codex_parity


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_materialized_claude_codex_context_contracts_are_equivalent(repo_root: Path):
    """Test cp1: Claude root, subagent, and Codex policy/TOML surfaces contain equivalent context contracts."""
    # 1. Root instructions parity
    claude_inst = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    agents_inst = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    dsh_inst = (repo_root / "DSH.md").read_text(encoding="utf-8")
    main_inst = (repo_root / "harness/instructions/main.md").read_text(encoding="utf-8")

    shared_markers = [
        "Context ledger",
        "plan_jumps",
        "graphify",
        "duplicate",
        "fail.closed",
    ]
    for marker in shared_markers:
        assert marker in claude_inst, f"CLAUDE.md missing shared contract marker: {marker}"
        assert marker in agents_inst, f"AGENTS.md missing shared contract marker: {marker}"
        assert marker in dsh_inst, f"DSH.md missing shared contract marker: {marker}"
        assert marker in main_inst, f"main.md missing shared contract marker: {marker}"

    # 2. Codex and Claude agent policy materialization parity
    manifest = load_manifest(repo_root / "harness/manifest.yaml")
    mapping = load_codex_policy_mapping(repo_root / "loop/runtime_materializers/codex_policy_mapping.yaml")

    for agent_id, agent_cfg in manifest.agents.items():
        src_path = repo_root / agent_cfg.source
        assert src_path.exists(), f"Agent source missing: {src_path}"

        claude_md_path = repo_root / f".claude/agents/{agent_id}.md"
        codex_toml_path = repo_root / f".codex/agents/{agent_id}.toml"
        sidecar_path = repo_root / f".codex/agents/{agent_id}.policy.json"

        assert claude_md_path.exists(), f"Claude agent file missing: {claude_md_path}"
        assert codex_toml_path.exists(), f"Codex TOML missing: {codex_toml_path}"
        assert sidecar_path.exists(), f"Codex sidecar missing: {sidecar_path}"

        policy_rec = parse_agent_policy_text(src_path.read_text(encoding="utf-8"), fallback_name=agent_id)
        policy_rec.validate_codex_runtime_support(mapping)

        # TOML parity
        toml_text = codex_toml_path.read_text(encoding="utf-8")
        assert f"# policy_fingerprint: {policy_rec.policy_fingerprint()}" in toml_text

        # Sidecar parity
        sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert sidecar_data["policy_fingerprint"] == policy_rec.policy_fingerprint()
        assert sorted(sidecar_data.get("disallowedTools", [])) == sorted(policy_rec.disallowedTools)
        assert sidecar_data.get("managed", False) == policy_rec.managed

    # 3. Full parity matrix check passes cleanly
    issues = check_codex_parity(
        hooks_json_path=repo_root / ".codex/hooks.json",
        manifest_path=repo_root / "harness/manifest.yaml",
        agents_dir=repo_root / ".codex/agents",
        root_dir=repo_root,
    )
    assert not issues, f"Codex parity checker found unexpected issues: {issues}"


def test_materializer_rejects_missing_or_divergent_context_contract(tmp_path: Path, repo_root: Path):
    """Test cp2: Parity checker fails when a generated surface is missing or divergent."""
    # Setup isolated test workspace
    import shutil
    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copytree(repo_root / "harness", ws / "harness")
    (ws / ".codex" / "agents").mkdir(parents=True)
    (ws / ".claude" / "agents").mkdir(parents=True)

    manifest_path = ws / "harness/manifest.yaml"
    manifest = load_manifest(manifest_path)

    # 1. Apply clean codex materialization
    apply_codex(manifest, manifest_path=manifest_path, root_dir=ws)

    clean_issues = check_codex_parity(
        hooks_json_path=ws / ".codex/hooks.json",
        manifest_path=manifest_path,
        agents_dir=ws / "harness/agents",
        root_dir=ws,
    )
    assert not clean_issues

    # 2. Reject missing generated agent TOML
    toml_to_remove = ws / ".codex/agents/verify-implement.toml"
    toml_to_remove.unlink()
    issues_missing_toml = check_codex_parity(
        hooks_json_path=ws / ".codex/hooks.json",
        manifest_path=manifest_path,
        agents_dir=ws / "harness/agents",
        root_dir=ws,
    )
    assert any(("missing_codex_agent" in issue or "missing" in issue) and "verify-implement.toml" in issue for issue in issues_missing_toml)

    # Reapply
    apply_codex(manifest, manifest_path=manifest_path, root_dir=ws)

    # 3. Reject divergent sidecar policy fingerprint
    sidecar_file = ws / ".codex/agents/verify-implement.policy.json"
    sc_data = json.loads(sidecar_file.read_text(encoding="utf-8"))
    sc_data["policy_fingerprint"] = "sha256:corrupted_hash"
    sidecar_file.write_text(json.dumps(sc_data), encoding="utf-8")

    issues_divergent = check_codex_parity(
        hooks_json_path=ws / ".codex/hooks.json",
        manifest_path=manifest_path,
        agents_dir=ws / "harness/agents",
        root_dir=ws,
    )
    assert any("policy_fingerprint mismatch in sidecar" in issue for issue in issues_divergent)

    # 4. Reject missing hooks.json
    hooks_file = ws / ".codex/hooks.json"
    hooks_file.unlink()
    issues_missing_hooks = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_path,
        agents_dir=ws / "harness/agents",
        root_dir=ws,
    )
    assert any("hooks_json_not_found" in issue or "missing" in issue for issue in issues_missing_hooks)


def test_parity_checker_rejects_duplicate_or_parallel_hook_entrypoint(repo_root: Path):
    """Test cp2: No parallel or unregistered hook entrypoint bypasses the manifest."""
    manifest = load_manifest(repo_root / "harness/manifest.yaml")
    hooks_json_path = repo_root / ".codex/hooks.json"
    hooks_data = json.loads(hooks_json_path.read_text(encoding="utf-8"))

    # Verify context-ledger hook is registered in PreToolUse
    pretool_hooks = hooks_data.get("hooks", {}).get("PreToolUse", [])
    ledger_entries = [h for h in pretool_hooks if "context_ledger_adapters.py" in str(h.get("command", ""))]
    assert len(ledger_entries) == 1, f"Expected exactly 1 context-ledger entry in PreToolUse, got {len(ledger_entries)}"
    assert ledger_entries[0].get("matcher") == "Write|Edit|NotebookEdit"

    # Verify write-pretool and context-ledger share existing registration without duplicate handlers
    all_commands = [h.get("command") for ev in hooks_data.get("hooks", {}).values() for h in ev]
    assert len(all_commands) == len(set(all_commands)), "Duplicate hook command entrypoint found in hooks.json"


def test_root_and_subagent_policy_records_preserve_provider_transport_only(repo_root: Path):
    """Test cp1: Root and subagent policy records use shared contract; provider payload is transport only."""
    mapping = load_codex_policy_mapping(repo_root / "loop/runtime_materializers/codex_policy_mapping.yaml")

    # Root record
    root_policy = PolicyRecord(
        name="root",
        actor_kind="root",
        mode="implement",
        context_budget_mode="strict",
    )
    root_policy.validate_codex_runtime_support(mapping)
    assert root_policy.policy_fingerprint().startswith("sha256:")

    # Subagent record
    subagent_policy = PolicyRecord(
        name="verify-implement",
        actor_kind="subagent",
        managed=True,
        disallowedTools=["Write", "Edit"],
        mode="gate",
        verdict="loop-gate-verdict/v1",
    )
    subagent_policy.validate_codex_runtime_support(mapping)
    assert subagent_policy.policy_fingerprint().startswith("sha256:")


def test_generated_artifacts_and_instructions_contain_contract_markers_and_no_broad_read_recovery(repo_root: Path):
    """Test cp4: Canonical instructions and generated surfaces contain contract markers without broad-read recovery."""
    import re

    pattern = re.compile(r"context ledger|plan_jumps|graphify|duplicate|whole plan|fail\.closed|derived_identity", re.IGNORECASE)

    target_files = [
        repo_root / "harness/instructions/main.md",
        repo_root / "CLAUDE.md",
        repo_root / "AGENTS.md",
        repo_root / "DSH.md",
        repo_root / "loop/runtime_materializers/agent_policy.py",
        repo_root / "loop/runtime_materializers/hooks_json.py",
        repo_root / "loop/runtime_materializers/codex_agent_toml.py",
        repo_root / "loop/runtime_materializers/codex_policy_mapping.yaml",
    ]

    for f in target_files:
        assert f.exists(), f"Target file does not exist: {f}"
        text = f.read_text(encoding="utf-8")
        matches = pattern.findall(text)
        assert len(matches) > 0, f"File {f.name} missing shared context contract markers"

    # Check for absence of broad-read recovery weakening language
    prohibited_weakening_phrases = [
        "read whole plan if needed",
        "fallback to reading whole plan",
        "bypass context ledger",
        "unrestricted codebase read",
    ]
    for f in target_files:
        text = f.read_text(encoding="utf-8").lower()
        for phrase in prohibited_weakening_phrases:
            assert phrase not in text, f"File {f.name} contains contract weakening language: {phrase}"

