import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
import yaml

from loop.runtime_materializers.hooks_json import CODEX_MIN_VERSION
from loop.runtime_materializers.parity import REQUIRED_CODEX_EVENTS, check_codex_parity


def test_required_codex_events_defined():
    assert len(REQUIRED_CODEX_EVENTS) >= 7
    expected_events = {"Stop", "SubagentStop", "PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart", "SubagentStart"}
    assert expected_events <= REQUIRED_CODEX_EVENTS



def test_codex_min_version_doctor():
    assert CODEX_MIN_VERSION == "0.152.0"
    parts = [int(p) for p in CODEX_MIN_VERSION.split(".")]
    assert len(parts) == 3
    assert parts[0] >= 0
    assert parts[1] >= 152


def test_check_codex_parity_missing_event(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = tmp_path / "hooks.json"
    actual_hooks = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    modified_hooks = copy.deepcopy(actual_hooks)
    modified_hooks["hooks"].pop("Stop", None)
    hooks_file.write_text(json.dumps(modified_hooks), encoding="utf-8")

    issues = check_codex_parity(hooks_file)
    assert any("missing_required_event: Stop" in issue for issue in issues)


def test_check_codex_parity_full_set():
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = repo_root / ".codex" / "hooks.json"
    manifest_file = repo_root / "harness" / "manifest.yaml"

    issues = check_codex_parity(hooks_file, manifest_file)
    assert issues == []


def test_runtime_sync_cli_check_missing_event_fails(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = tmp_path / "hooks.json"
    actual_hooks = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    modified_hooks = copy.deepcopy(actual_hooks)
    modified_hooks["hooks"].pop("Stop", None)
    hooks_file.write_text(json.dumps(modified_hooks), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "loop.cli.runtime_sync", "--check", "--hooks-json", str(hooks_file)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "missing_required_event: Stop" in proc.stdout or "missing_required_event: Stop" in proc.stderr


def test_runtime_sync_cli_check_full_set_succeeds():
    proc = subprocess.run(
        [sys.executable, "-m", "loop.cli.runtime_sync", "--check", "--runtime", "codex"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "No drift detected" in proc.stdout


def test_orphan_agent_md_fails_parity(tmp_path):
    """FR-004 / TM-004 / US-004 / SC-003: undeclared harness/agents/*.md fails parity."""
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = repo_root / ".codex" / "hooks.json"
    manifest_file = repo_root / "harness" / "manifest.yaml"

    # Create dummy agents dir with an orphan prompt file
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "orphan-agent.md").write_text("# Orphan prompt\n", encoding="utf-8")

    issues = check_codex_parity(hooks_file, manifest_file, agents_dir=agents_dir)
    assert any("missing_manifest_agent: orphan-agent" in issue or "orphan" in issue for issue in issues)


def test_parity_source_is_agents_glob_not_allowlist_only():
    """FR-004: All harness/agents/*.md are checked against manifest."""
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = repo_root / ".codex" / "hooks.json"
    manifest_file = repo_root / "harness" / "manifest.yaml"
    agents_dir = repo_root / "harness" / "agents"

    issues = check_codex_parity(hooks_file, manifest_file, agents_dir=agents_dir)
    assert issues == []


def test_declared_video_prompts_not_orphan():
    """s02 consume: video prompts in harness/agents are declared and not orphans."""
    repo_root = Path(__file__).resolve().parents[2]
    hooks_file = repo_root / ".codex" / "hooks.json"
    manifest_file = repo_root / "harness" / "manifest.yaml"
    agents_dir = repo_root / "harness" / "agents"

    issues = check_codex_parity(hooks_file, manifest_file, agents_dir=agents_dir)
    assert not any("verify-script" in issue or "verify-edit" in issue or "verify-publish" in issue for issue in issues)


def _setup_claude_manifest_env(tmp_path: Path):
    manifest_file = tmp_path / "harness" / "manifest.yaml"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_content = """schema_version: "harness-manifest/v1"
agents: {}
hooks: {}
instructions:
  main:
    source: "harness/instructions/main.md"
    runtimes:
      claude:
        target: "CLAUDE.md"
"""
    manifest_file.write_text(manifest_content, encoding="utf-8")
    source_inst = tmp_path / "harness" / "instructions" / "main.md"
    source_inst.parent.mkdir(parents=True, exist_ok=True)
    source_inst.write_text("# Main instructions\n", encoding="utf-8")
    return manifest_file


def test_claude_check_hash_mismatch_fails(tmp_path):
    """FR-007 / Failure matrix TM-005: hash_mismatch on CLAUDE.md exits non-zero."""
    manifest_file = _setup_claude_manifest_env(tmp_path)
    dest_claude = tmp_path / "CLAUDE.md"
    dest_claude.write_text("# Stale modified instructions\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "claude",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "hash_mismatch" in proc.stdout or "hash_mismatch" in proc.stderr
    assert "CLAUDE.md" in proc.stdout or "CLAUDE.md" in proc.stderr


def test_claude_check_not_warning_only(tmp_path):
    """AC-5: No warning-only exit 0 on hash_mismatch."""
    manifest_file = _setup_claude_manifest_env(tmp_path)
    dest_claude = tmp_path / "CLAUDE.md"
    dest_claude.write_text("# Stale unregenerated instructions\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "claude",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "Drift/parity issues detected" in proc.stderr


def test_claude_check_matching_or_generated_header_passes(tmp_path):
    """Product WHAT #5: Matching content or documented generated header passes check."""
    manifest_file = _setup_claude_manifest_env(tmp_path)
    dest_claude = tmp_path / "CLAUDE.md"

    # Case 1: Matching content
    dest_claude.write_text("# Main instructions\n", encoding="utf-8")
    proc1 = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "claude",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc1.returncode == 0
    assert "No drift detected" in proc1.stdout

    # Case 2: Documented generated header marker
    dest_claude.write_text(
        "<!-- GENERATED by runtime-sync from harness/instructions/main.md — DO NOT EDIT -->\n# Custom extended instructions\n",
        encoding="utf-8",
    )
    proc2 = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "claude",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc2.returncode == 0
    assert "No drift detected" in proc2.stdout


def test_claude_check_allow_hash_mismatch_flag(tmp_path):
    """Allow flag allows hash mismatch without non-zero exit when explicitly requested."""
    manifest_file = _setup_claude_manifest_env(tmp_path)
    dest_claude = tmp_path / "CLAUDE.md"
    dest_claude.write_text("# Stale unregenerated instructions\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "claude",
            "--check",
            "--allow-hash-mismatch",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "allowed via flag" in proc.stderr or "No drift detected" in proc.stdout


def _setup_codex_manifest_env(tmp_path: Path):
    manifest_file = tmp_path / "harness" / "manifest.yaml"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    agents_dir = tmp_path / "harness" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = tmp_path / ".codex" / "agents"
    codex_dir.mkdir(parents=True, exist_ok=True)

    agent_md = agents_dir / "verify-implement.md"
    agent_md.write_text(
        "---\nname: verify-implement\ndescription: Gate\ndisallowedTools: [Write, Edit]\nmanaged: true\n---\nBody",
        encoding="utf-8",
    )

    manifest_data = {
        "schema_version": "harness-manifest/v1",
        "description": "Test manifest",
        "agents": {
            "verify-implement": {
                "description": "Gate",
                "source": "harness/agents/verify-implement.md",
                "runtimes": {
                    "codex": {
                        "type": "materialize",
                        "target": ".codex/agents/verify-implement.toml",
                    }
                },
            }
        },
        "hooks": {},
        "instructions": {},
    }
    manifest_file.write_text(yaml.dump(manifest_data), encoding="utf-8")

    from loop.runtime_materializers.codex_sync import apply_codex
    from loop.runtime_materializers.manifest_schema import load_manifest

    manifest = load_manifest(manifest_file)
    apply_codex(manifest, manifest_path=manifest_file, root_dir=tmp_path)
    return manifest_file


def test_runtime_sync_check_fails_on_stripped_fingerprint(tmp_path: Path):
    """FR-012 / Failure TM-006: runtime-sync --check fails on stripped fingerprint."""
    manifest_file = _setup_codex_manifest_env(tmp_path)
    dest_toml = tmp_path / ".codex" / "agents" / "verify-implement.toml"
    assert dest_toml.exists()

    # Strip fingerprint comment
    lines = [
        line
        for line in dest_toml.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith("# policy_fingerprint:")
    ]
    dest_toml.write_text("".join(lines), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "codex",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "hash_mismatch" in proc.stdout or "hash_mismatch" in proc.stderr or "Drift/parity issues detected" in proc.stderr


def test_runtime_sync_check_fails_on_missing_sidecar(tmp_path: Path):
    """FR-012 / Failure TM-006: runtime-sync --check fails on missing sidecar policy.json."""
    manifest_file = _setup_codex_manifest_env(tmp_path)
    dest_sidecar = tmp_path / ".codex" / "agents" / "verify-implement.policy.json"
    assert dest_sidecar.exists()
    dest_sidecar.unlink()

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "loop.cli.runtime_sync",
            "--manifest",
            str(manifest_file),
            "--root-dir",
            str(tmp_path),
            "--runtime",
            "codex",
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "missing_dest" in proc.stdout or "missing_dest" in proc.stderr or "Drift/parity issues detected" in proc.stderr


def test_kind_i_no_toml_equals_full_agent_instruction():
    """Kind I / CP2 / CP3: prod instructions do not teach Codex TOML = full agent or invented deny CLI flags."""
    repo_root = Path(__file__).resolve().parents[2]
    readme_path = repo_root / "loop" / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        assert "TOML = full" not in content
        assert "toml equals" not in content.lower()
        assert "presence.only" not in content
