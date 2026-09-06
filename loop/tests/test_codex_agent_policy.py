from __future__ import annotations

from pathlib import Path
import pytest

from loop.runtime_materializers.agent_policy import (
    PolicyRecord,
    parse_agent_policy,
    parse_agent_policy_text,
    AgentPolicyError,
)


def test_PolicyRecord_fields_fr001():
    record = PolicyRecord(
        name="verify-implement",
        description="Gate verify",
        tools=["Read", "Grep", "Bash"],
        disallowedTools=["Write", "Edit", "Agent"],
        maxTurns=15,
        overlay="@gate-repair",
        managed=True,
        mode="implement",
        verdict="PASS/FAIL",
        allow_worktree=False,
        requires_model="claude-3-7-sonnet",
        default_loop=False,
        default_chat=False,
        color="blue",
    )
    assert record.name == "verify-implement"
    assert record.disallowedTools == ["Write", "Edit", "Agent"]
    assert record.managed is True
    assert record.maxTurns == 15
    assert record.color == "blue"


def test_parse_frontmatter_disallowed_tools():
    md_content = """---
name: verify-implement
description: Pre-FINISH verify gate for IMPLEMENT/REFACTOR/TASK
tools: [Read, Grep, Bash]
disallowedTools: [Write, Edit, Agent]
managed: true
mode: implement
verdict: PASS/FAIL
allow_worktree: false
---
Instructions body here.
"""
    record = parse_agent_policy_text(md_content, fallback_name="verify-implement")
    assert record.name == "verify-implement"
    assert record.disallowedTools == ["Write", "Edit", "Agent"]
    assert record.tools == ["Read", "Grep", "Bash"]
    assert record.managed is True


def test_parse_real_verify_implement_agent():
    repo_root = Path(__file__).resolve().parent.parent.parent
    agent_path = repo_root / "harness" / "agents" / "verify-implement.md"
    record = parse_agent_policy(agent_path)
    assert record.name == "verify-implement"
    assert record.managed is True
    assert "Write" in record.disallowedTools
    assert "Edit" in record.disallowedTools
    assert "Agent" in record.disallowedTools
    assert "Read" in record.tools
    assert record.mode == "gate"


def test_parse_real_gate_repair_agent():
    repo_root = Path(__file__).resolve().parent.parent.parent
    agent_path = repo_root / "harness" / "agents" / "gate-repair.md"
    record = parse_agent_policy(agent_path)
    assert record.name == "gate-repair"
    assert record.managed is True
    assert "Agent" in record.disallowedTools
    assert "Write" in record.tools
    assert record.mode == "repair"


def test_extra_unknown_frontmatter_listed_not_silent():
    md_content = """---
name: custom-agent
description: Managed with unknown field
managed: true
unknown_custom_field: 123
another_alien_key: true
---
Body text
"""
    with pytest.raises(AgentPolicyError) as exc_info:
        parse_agent_policy_text(md_content, fallback_name="custom-agent")
    err_msg = str(exc_info.value)
    assert "unknown_custom_field" in err_msg or "extra" in err_msg


def test_unmanaged_unknown_frontmatter_allowed_or_listed():
    md_content = """---
name: unmanaged-agent
description: Unmanaged with unknown field
managed: false
unknown_custom_field: 123
---
Body text
"""
    record = parse_agent_policy_text(md_content, fallback_name="unmanaged-agent")
    assert record.name == "unmanaged-agent"
    assert "unknown_custom_field" in record.extra_fields


def test_silent_drop_denied_retains_disallowed_tools():
    md_content = """---
name: verify-implement
description: Gate verify
disallowedTools: [Write, Edit, Agent]
managed: true
---
Body
"""
    record = parse_agent_policy_text(md_content, fallback_name="verify-implement")
    # Red check / retention check: disallowedTools must be accurately retained
    assert record.disallowedTools == ["Write", "Edit", "Agent"]
    assert len(record.disallowedTools) == 3


def test_policy_fingerprint_generation():
    record = PolicyRecord(
        name="verify-implement",
        description="Gate verify",
        tools=["Read", "Grep", "Bash"],
        disallowedTools=["Write", "Edit", "Agent"],
        managed=True,
    )
    fp = record.policy_fingerprint()
    assert fp.startswith("sha256:")
    assert len(fp) == 7 + 64


def test_mapping_yaml_required_deny_has_hook_or_native():
    from loop.runtime_materializers.agent_policy import load_codex_policy_mapping

    mapping = load_codex_policy_mapping()
    assert mapping.schema_version == "codex-policy-mapping/v1"
    assert "disallowedTools" in mapping.fields
    deny_field = mapping.fields["disallowedTools"]
    assert deny_field.support in ("native", "hook")
    assert deny_field.support != "unsupported"


def test_mapping_native_fields_are_real_codex_toml_no_invented_flags():
    from loop.runtime_materializers.agent_policy import load_codex_policy_mapping

    mapping = load_codex_policy_mapping()
    allowed_codex_toml_native = {"name", "description", "developer_instructions"}
    for field_name, field_map in mapping.fields.items():
        if field_map.support == "native":
            assert field_map.target in allowed_codex_toml_native, (
                f"FR-011 violation: Invented native target {field_map.target} for field {field_name}"
            )


def test_materialize_unsupported_runtime_policy_without_hook_fails():
    from loop.runtime_materializers.agent_policy import (
        CodexPolicyMapping,
        PolicyFieldMapping,
        PolicyRecord,
        UnsupportedRuntimePolicyError,
    )

    record = PolicyRecord(
        name="verify-implement",
        description="Gate",
        disallowedTools=["Write", "Edit", "Agent"],
        managed=True,
    )
    # Mapping with unsupported disallowedTools
    fake_mapping = CodexPolicyMapping(
        fields={
            "disallowedTools": PolicyFieldMapping(support="unsupported"),
        }
    )
    with pytest.raises(UnsupportedRuntimePolicyError) as exc_info:
        record.validate_codex_runtime_support(fake_mapping)
    assert "unsupported_runtime_policy" in str(exc_info.value)


def test_mutation_strip_disallowed_tools_fails_parity_drop_deny(tmp_path: Path):
    """TM-001 / FR-013 / cp1: Drop disallowedTools from sidecar or TOML → parity fails."""
    import json
    from loop.runtime_materializers.parity import check_codex_parity

    # Setup a minimal manifest and agent layout in tmp_path
    repo_root = Path(__file__).resolve().parents[2]
    harness_dir = tmp_path / "harness"
    agents_dir = harness_dir / "agents"
    agents_dir.mkdir(parents=True)
    agent_md = agents_dir / "verify-implement.md"
    agent_md.write_text(
        "---\nname: verify-implement\ndescription: Gate\ndisallowedTools: [Write, Edit]\nmanaged: true\n---\nBody",
        encoding="utf-8",
    )

    manifest_file = harness_dir / "manifest.yaml"
    manifest_file.write_text(
        """schema_version: "harness-manifest/v1"
instructions: {}
agents:
  verify-implement:
    description: "Gate"
    source: harness/agents/verify-implement.md
    runtimes:
      claude:
        target: .claude/agents/verify-implement.md
      codex:
        target: .codex/agents/verify-implement.toml
        materialize: true
hooks:
  session-start:
    source: "harness/hooks/session-start.py"
    runtimes:
      codex:
        hooks_json_entry: true
  user-prompt:
    source: "harness/hooks/user-prompt.py"
    runtimes:
      codex:
        hooks_json_entry: true
  agent-pretool:
    source: "harness/hooks/agent-pretool.py"
    runtimes:
      codex:
        hooks_json_entry: true
  bash-pretool:
    source: "harness/hooks/bash-pretool.py"
    runtimes:
      codex:
        hooks_json_entry: true
  write-pretool:
    source: "harness/hooks/write-pretool.py"
    runtimes:
      codex:
        hooks_json_entry: true
  agent-posttool:
    source: "harness/hooks/agent-posttool.py"
    runtimes:
      codex:
        hooks_json_entry: true
  bash-output-cap:
    source: "harness/hooks/bash-output-cap.py"
    runtimes:
      codex:
        hooks_json_entry: true
  subagent-stop:
    source: "harness/hooks/subagent-stop.py"
    runtimes:
      codex:
        hooks_json_entry: true
  subagent-start:
    source: "harness/hooks/subagent-start.py"
    runtimes:
      codex:
        hooks_json_entry: true
  stop-gate:
    source: "harness/hooks/stop-gate.py"
    runtimes:
      codex:
        hooks_json_entry: true
""",
        encoding="utf-8",
    )

    # Materialize properly first
    from loop.runtime_materializers.manifest_schema import load_manifest
    from loop.runtime_materializers.agents import materialize_agents
    from loop.runtime_materializers.hooks_json import generate_hooks_json

    man = load_manifest(manifest_file)
    materialize_agents(man, "codex", dest_root=tmp_path, repo_root=tmp_path)

    hooks_file = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(man, manifest_file, hooks_file, repo_root=repo_root)

    # Clean parity check should pass
    clean_issues = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_file,
        agents_dir=agents_dir,
        root_dir=tmp_path,
    )
    assert not clean_issues, f"Expected no issues, got: {clean_issues}"

    # Mutation 1: Strip disallowedTools from sidecar JSON
    sidecar_file = tmp_path / ".codex" / "agents" / "verify-implement.policy.json"
    sc_data = json.loads(sidecar_file.read_text(encoding="utf-8"))
    sc_data["disallowedTools"] = []
    sidecar_file.write_text(json.dumps(sc_data), encoding="utf-8")

    mutated_issues = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_file,
        agents_dir=agents_dir,
        root_dir=tmp_path,
    )
    assert any("codex_policy_dropped" in issue and "disallowedTools mismatch" in issue for issue in mutated_issues)

    # Mutation 2: Remove sidecar file entirely
    sidecar_file.unlink()
    missing_sc_issues = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_file,
        agents_dir=agents_dir,
        root_dir=tmp_path,
    )
    assert any("codex_policy_dropped" in issue and "missing sidecar" in issue for issue in missing_sc_issues)


def test_verify_implement_mapping_not_weaker_than_md():
    """TM-003 / US-001 / SC-005 / cp2: verify-implement Codex not weaker than md; hook row exists for disallowedTools."""
    from loop.runtime_materializers.agent_policy import load_codex_policy_mapping, parse_agent_policy

    mapping = load_codex_policy_mapping()
    assert "disallowedTools" in mapping.fields
    field_map = mapping.fields["disallowedTools"]
    # If not native, must be hook enforcement backed by hook target
    assert field_map.support in ("native", "hook")
    if field_map.support == "hook":
        assert field_map.target is not None
        assert Path(field_map.target).exists()

    # Check verify-implement agent md
    repo_root = Path(__file__).resolve().parents[2]
    agent_md = repo_root / "harness" / "agents" / "verify-implement.md"
    record = parse_agent_policy(agent_md)
    assert "Write" in record.disallowedTools
    assert "Edit" in record.disallowedTools
    assert "Agent" in record.disallowedTools
    # Validate that mapping validates successfully against our record
    record.validate_codex_runtime_support(mapping)


def test_explorer_write_denied_in_policy():
    """FR-010 / TM-006 / cp3: explorer Codex Write denied in policy frontmatter and mapping."""
    from loop.runtime_materializers.agent_policy import load_codex_policy_mapping, parse_agent_policy

    repo_root = Path(__file__).resolve().parents[2]
    agent_md = repo_root / "harness" / "agents" / "explorer.md"
    record = parse_agent_policy(agent_md)
    assert "Write" in record.disallowedTools
    assert "Edit" in record.disallowedTools

    mapping = load_codex_policy_mapping()
    record.validate_codex_runtime_support(mapping)


def test_presence_only_toml_not_sufficient_for_parity(tmp_path: Path):
    """AC-1 / AC-5 / cp4: Presence-only TOML file without policy fingerprint / valid sidecar fails parity."""
    import json
    from loop.runtime_materializers.parity import check_codex_parity

    harness_dir = tmp_path / "harness"
    agents_dir = harness_dir / "agents"
    agents_dir.mkdir(parents=True)
    agent_md = agents_dir / "verify-implement.md"
    agent_md.write_text(
        "---\nname: verify-implement\ndescription: Gate\ndisallowedTools: [Write, Edit]\nmanaged: true\n---\nBody",
        encoding="utf-8",
    )

    manifest_file = harness_dir / "manifest.yaml"
    manifest_file.write_text(
        """schema_version: "harness-manifest/v1"
instructions: {}
agents:
  verify-implement:
    description: "Gate"
    source: harness/agents/verify-implement.md
    runtimes:
      claude:
        target: .claude/agents/verify-implement.md
      codex:
        target: .codex/agents/verify-implement.toml
        materialize: true
hooks: {}
""",
        encoding="utf-8",
    )

    # Presence-only: write a dummy TOML that has name/description but lacks policy_fingerprint comment and sidecar
    toml_file = tmp_path / ".codex" / "agents" / "verify-implement.toml"
    toml_file.parent.mkdir(parents=True, exist_ok=True)
    toml_file.write_text(
        'name = "verify-implement"\ndescription = "Gate"\ndeveloper_instructions = "Body"\n',
        encoding="utf-8",
    )

    hooks_file = tmp_path / ".codex" / "hooks.json"
    hooks_file.write_text(
        json.dumps({
            "hooks": {
                "Stop": [],
                "SubagentStop": [],
                "PreToolUse": [],
                "PostToolUse": [],
                "UserPromptSubmit": [],
                "SessionStart": [],
                "SubagentStart": [],
            }
        }),
        encoding="utf-8",
    )
    meta_file = tmp_path / ".codex" / "hooks.meta.json"
    import hashlib
    meta_file.write_text(
        json.dumps({"manifest_hash": hashlib.sha256(manifest_file.read_bytes()).hexdigest()}),
        encoding="utf-8",
    )

    issues = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_file,
        root_dir=tmp_path,
    )
    assert issues, "Presence-only TOML must fail parity!"
    assert any("codex_policy_dropped" in issue for issue in issues)


def test_contracts_checksum_drift_fails_closed():
    """TM-002 / US-003 / SC-003: check_contract_drift fails on mutated CONTRACTS."""
    from harness.hooks._lib import CONTRACTS, CONTRACTS_SHA256, check_contract_drift

    # Test all known agents match
    for agent_name in CONTRACTS:
        ok, msg = check_contract_drift(agent_name)
        assert ok is True, f"Contract drift detected on fresh checkout for {agent_name}: {msg}"

    # Mutate one and verify failure
    orig = CONTRACTS["verify"]
    try:
        CONTRACTS["verify"] = orig + "\n# mutated line"
        ok, msg = check_contract_drift("verify")
        assert ok is False
        assert "agent_contract_drift" in msg
    finally:
        CONTRACTS["verify"] = orig


def test_no_presence_only_parity_green_after_purge(tmp_path: Path):
    """s07 TDD 1: Presence-only checks alone never green when policy/fingerprint is corrupted."""
    import json
    from loop.runtime_materializers.parity import check_codex_parity

    harness_dir = tmp_path / "harness"
    agents_dir = harness_dir / "agents"
    agents_dir.mkdir(parents=True)
    agent_md = agents_dir / "verify-implement.md"
    agent_md.write_text(
        "---\nname: verify-implement\ndescription: Gate\ndisallowedTools: [Write, Edit]\nmanaged: true\n---\nBody",
        encoding="utf-8",
    )

    manifest_file = harness_dir / "manifest.yaml"
    manifest_file.write_text(
        """schema_version: "harness-manifest/v1"
instructions: {}
agents:
  verify-implement:
    description: "Gate"
    source: harness/agents/verify-implement.md
    runtimes:
      claude:
        target: .claude/agents/verify-implement.md
      codex:
        target: .codex/agents/verify-implement.toml
        materialize: true
hooks: {}
""",
        encoding="utf-8",
    )

    # Corrupt sidecar (e.g. drop disallowedTools)
    toml_file = tmp_path / ".codex" / "agents" / "verify-implement.toml"
    toml_file.parent.mkdir(parents=True, exist_ok=True)
    toml_file.write_text(
        '# policy_fingerprint: sha256:corrupted\nname = "verify-implement"\ndescription = "Gate"\ndeveloper_instructions = "Body"\n',
        encoding="utf-8",
    )
    sidecar_file = tmp_path / ".codex" / "agents" / "verify-implement.policy.json"
    sidecar_file.write_text(
        json.dumps({
            "name": "verify-implement",
            "policy_fingerprint": "sha256:corrupted",
            "disallowedTools": [],
        }),
        encoding="utf-8",
    )

    hooks_file = tmp_path / ".codex" / "hooks.json"
    hooks_file.write_text(
        json.dumps({
            "hooks": {
                "Stop": [],
                "SubagentStop": [],
                "PreToolUse": [],
                "PostToolUse": [],
                "UserPromptSubmit": [],
                "SessionStart": [],
                "SubagentStart": [],
            }
        }),
        encoding="utf-8",
    )
    meta_file = tmp_path / ".codex" / "hooks.meta.json"
    import hashlib
    meta_file.write_text(
        json.dumps({"manifest_hash": hashlib.sha256(manifest_file.read_bytes()).hexdigest()}),
        encoding="utf-8",
    )

    issues = check_codex_parity(
        hooks_json_path=hooks_file,
        manifest_path=manifest_file,
        root_dir=tmp_path,
    )
    assert issues, "Corrupted policy must not pass parity even if TOML exists"
    assert any("codex_policy_dropped" in issue for issue in issues)


def test_no_software_only_always_inject_exclusive():
    """s07 TDD 2: ALWAYS_INJECT is not restricted to legacy software-only agents."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("subagent_start", "harness/hooks/subagent-start.py")
    assert spec is not None and spec.loader is not None
    subagent_start_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subagent_start_mod)

    active_inject = getattr(subagent_start_mod, "_ALWAYS_INJECT", None)
    if active_inject is None:
        active_inject = subagent_start_mod.get_always_inject_set()

    assert "verify-edit" in active_inject
    assert "sunset-inventory" in active_inject


def test_no_silent_drop_disallowed_tools_prod_path():
    """s07 TDD 3: Materializing agent policy validates and retains disallowedTools."""
    from loop.runtime_materializers.agent_policy import parse_agent_policy, load_codex_policy_mapping

    repo_root = Path(__file__).resolve().parents[2]
    agent_md = repo_root / "harness" / "agents" / "verify-implement.md"
    record = parse_agent_policy(agent_md)
    mapping = load_codex_policy_mapping()
    record.validate_codex_runtime_support(mapping)
    assert "Write" in record.disallowedTools
    assert "Edit" in record.disallowedTools
    assert "Agent" in record.disallowedTools
