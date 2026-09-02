import tempfile
from pathlib import Path

import pytest
import yaml

from loop.runtime_materializers.manifest_schema import HarnessManifest, load_manifest
from loop.runtime_materializers.sync import ApplyResult, DriftItem, ManifestSync, SyncTarget


@pytest.fixture
def sample_manifest_path(tmp_path: Path) -> Path:
    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "agents": {
            "agent-a": {
                "description": "Agent A",
                "source": "harness/agents/agent-a.md",
                "runtimes": {
                    "codex": {
                        "materialize": True,
                        "target": ".codex/agents/agent-a.toml",
                    },
                    "claude": {
                        "copy_to": ".claude/agents/agent-a.md",
                    },
                    "dsh": {
                        "profile_preset": "agent-a",
                    },
                },
            }
        },
        "hooks": {
            "stop-gate": {
                "source": "harness/hooks/stop-gate.py",
                "runtimes": {
                    "codex": {
                        "hooks_json_entry": True,
                    },
                    "claude": {
                        "settings_key": "hooks.StopGate",
                    },
                },
            }
        },
        "instructions": {
            "main": {
                "source": "harness/instructions/main.md",
                "runtimes": {
                    "codex": {
                        "target": "AGENTS.md",
                    },
                    "claude": {
                        "target": "CLAUDE.md",
                    },
                },
            }
        },
    }
    path = tmp_path / "harness" / "manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(manifest_data), encoding="utf-8")
    return path


def test_collect_targets_codex_returns_materialize(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    targets = sync.collect_targets("codex")

    # Should collect agent-a (materialize: True, target set) and instruction (target set)
    # Stop-gate hook has no target key, so it's not a file sync target for sync.py
    assert len(targets) == 2

    agent_targets = [t for t in targets if t.kind == "agent"]
    assert len(agent_targets) == 1
    assert agent_targets[0].source == root_dir / "harness/agents/agent-a.md"
    assert agent_targets[0].dest == root_dir / ".codex/agents/agent-a.toml"

    inst_targets = [t for t in targets if t.kind == "instruction"]
    assert len(inst_targets) == 1
    assert inst_targets[0].source == root_dir / "harness/instructions/main.md"
    assert inst_targets[0].dest == root_dir / "AGENTS.md"


def test_collect_targets_claude_native_skipped(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    # dsh runtime has profile_preset, no target or copy_to
    dsh_targets = sync.collect_targets("dsh")
    assert len(dsh_targets) == 0


def test_check_drift_missing_dest(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    # Create source file
    source_file = root_dir / "harness/agents/agent-a.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent content", encoding="utf-8")

    source_inst = root_dir / "harness/instructions/main.md"
    source_inst.parent.mkdir(parents=True, exist_ok=True)
    source_inst.write_text("instruction content", encoding="utf-8")

    drift = sync.check("codex")
    assert len(drift) == 2
    assert all(item.reason == "missing_dest" for item in drift)


def test_check_drift_hash_mismatch(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    source_file = root_dir / "harness/agents/agent-a.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent content v1", encoding="utf-8")

    dest_file = root_dir / ".codex/agents/agent-a.toml"
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text("agent content v2", encoding="utf-8")

    drift = sync.check("codex")
    agent_drift = [d for d in drift if d.target.kind == "agent"]
    assert len(agent_drift) == 1
    assert agent_drift[0].reason == "hash_mismatch"


def test_check_no_drift_when_up_to_date(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    source_file = root_dir / "harness/agents/agent-a.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent content", encoding="utf-8")

    dest_file = root_dir / ".codex/agents/agent-a.toml"
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text("agent content", encoding="utf-8")

    source_inst = root_dir / "harness/instructions/main.md"
    source_inst.parent.mkdir(parents=True, exist_ok=True)
    source_inst.write_text("instruction content", encoding="utf-8")

    dest_inst = root_dir / "AGENTS.md"
    dest_inst.write_text("instruction content", encoding="utf-8")

    drift = sync.check("codex")
    assert len(drift) == 0


def test_apply_returns_apply_result(sample_manifest_path: Path) -> None:
    root_dir = sample_manifest_path.parent.parent
    sync = ManifestSync.from_file(sample_manifest_path, root_dir=root_dir)

    source_file = root_dir / "harness/agents/agent-a.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("agent content v1", encoding="utf-8")

    source_inst = root_dir / "harness/instructions/main.md"
    source_inst.parent.mkdir(parents=True, exist_ok=True)
    source_inst.write_text("inst content v1", encoding="utf-8")

    # Dry run creation
    res_dry = sync.apply("codex", dry_run=True)
    assert res_dry.created == 2
    assert res_dry.updated == 0
    assert res_dry.skipped == 0
    assert not (root_dir / ".codex/agents/agent-a.toml").exists()

    # Actual apply creation
    res_live = sync.apply("codex", dry_run=False)
    assert res_live.created == 2
    assert res_live.updated == 0
    assert (root_dir / ".codex/agents/agent-a.toml").read_text(encoding="utf-8") == "agent content v1"

    # Modify one source for update
    source_file.write_text("agent content v2", encoding="utf-8")
    res_update = sync.apply("codex", dry_run=False)
    assert res_update.created == 0
    assert res_update.updated == 1
    assert res_update.skipped == 1
    assert (root_dir / ".codex/agents/agent-a.toml").read_text(encoding="utf-8") == "agent content v2"
