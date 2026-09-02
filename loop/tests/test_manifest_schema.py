from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from loop.runtime_materializers.manifest_schema import (
    load_manifest,
    ManifestValidationError,
    HarnessManifest,
    ManifestAgent,
    ManifestHook,
)

def test_load_valid_manifest(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "verify-implement": {
                "description": "Pre-FINISH verify gate for IMPLEMENT",
                "source": "harness/agents/verify-implement.md",
                "runtimes": {
                    "claude": {"copy_to": ".claude/agents/verify-implement.md"},
                    "codex": {"materialize": True, "target": ".codex/agents/verify-implement.toml"},
                },
            }
        },
        "hooks": {
            "stop-gate": {
                "source": "harness/hooks/stop-gate.py",
                "runtimes": {
                    "claude": {"settings_key": "hooks.StopGate"},
                    "codex": {"hooks_json_entry": True},
                },
            }
        },
        "instructions": {
            "main": {
                "source": "harness/instructions/main.md",
                "runtimes": {"claude": {"target": "CLAUDE.md"}},
            }
        },
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    assert manifest.schema_version == "harness-manifest/v1"
    assert "verify-implement" in manifest.agents
    assert "stop-gate" in manifest.hooks
    assert "main" in manifest.instructions


def test_invalid_schema_version_raises(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "invalid/v1",
        "agents": {},
        "hooks": {},
        "instructions": {},
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError) as exc_info:
        load_manifest(manifest_file)
    assert exc_info.value.exit_code == 2


def test_missing_required_section_raises(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {},
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError) as exc_info:
        load_manifest(manifest_file)
    assert exc_info.value.exit_code == 2


def test_agent_entry_codex_materialize(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "test-agent": {
                "description": "Test agent",
                "source": "harness/agents/test.md",
                "runtimes": {
                    "codex": {"materialize": True, "target": ".codex/agents/test.toml"}
                },
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    agent = manifest.agents["test-agent"]
    assert agent.runtimes["codex"].get("materialize") is True
    assert agent.runtimes["codex"].get("target") == ".codex/agents/test.toml"


def test_hook_entry_claude_settings_path(tmp_path: Path) -> None:
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {},
        "hooks": {
            "my-hook": {
                "source": "harness/hooks/my_hook.py",
                "runtimes": {
                    "claude": {"settings_key": "hooks.MyHook"}
                },
            }
        },
        "instructions": {},
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.safe_dump(manifest_data), encoding="utf-8")

    manifest = load_manifest(manifest_file)
    hook = manifest.hooks["my-hook"]
    assert hook.runtimes["claude"].get("settings_key") == "hooks.MyHook"
