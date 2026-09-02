from __future__ import annotations

import json
from pathlib import Path
import pytest
from loop.runtime_materializers.manifest_schema import load_manifest, HarnessManifest
from loop.runtime_materializers.hooks_json import generate_hooks_json, GENERATED_HEADER


@pytest.fixture
def sample_manifest_file(tmp_path: Path) -> Path:
    hooks_dir = tmp_path / "harness" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "stop-gate.py").write_text("# dummy", encoding="utf-8")
    (hooks_dir / "spawn_validate.py").write_text("# dummy", encoding="utf-8")
    (hooks_dir / "session-start.py").write_text("# dummy", encoding="utf-8")

    manifest_content = """
schema_version: "harness-manifest/v1"
agents: {}
hooks:
  stop-gate:
    source: "harness/hooks/stop-gate.py"
    runtimes:
      codex:
        hooks_json_entry: true
  spawn-validate:
    source: "harness/hooks/spawn_validate.py"
    runtimes:
      codex:
        hooks_json_entry: true
  session-start:
    source: "harness/hooks/session-start.py"
    runtimes:
      codex:
        hooks_json_entry: true
instructions: {}
"""
    p = tmp_path / "manifest.yaml"
    p.write_text(manifest_content.strip(), encoding="utf-8")
    return p


def test_generated_header_present(sample_manifest_file: Path, tmp_path: Path) -> None:
    manifest = load_manifest(sample_manifest_file)
    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)

    meta = json.loads((tmp_path / ".codex" / "hooks.meta.json").read_text(encoding="utf-8"))
    assert GENERATED_HEADER in meta["header"]


def test_manifest_hash_embedded(sample_manifest_file: Path, tmp_path: Path) -> None:
    import hashlib
    expected_hash = hashlib.sha256(sample_manifest_file.read_bytes()).hexdigest()

    manifest = load_manifest(sample_manifest_file)
    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert "_meta" not in data
    meta = json.loads((tmp_path / ".codex" / "hooks.meta.json").read_text(encoding="utf-8"))
    assert meta["manifest_hash"] == expected_hash


def test_stop_event_entrypoint(sample_manifest_file: Path, tmp_path: Path) -> None:
    manifest = load_manifest(sample_manifest_file)
    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert "hooks" in data
    hooks = data["hooks"]
    assert "Stop" in hooks
    assert "harness/hooks/stop-gate.py" in str(hooks["Stop"])


def test_user_prompt_submit_entrypoint(sample_manifest_file: Path, tmp_path: Path) -> None:
    manifest = load_manifest(sample_manifest_file)
    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)

    data = json.loads(dest.read_text(encoding="utf-8"))
    hooks = data["hooks"]
    assert "UserPromptSubmit" in hooks
    assert "harness/hooks/spawn_validate.py" in str(hooks["UserPromptSubmit"])


def test_generate_idempotent(sample_manifest_file: Path, tmp_path: Path) -> None:
    manifest = load_manifest(sample_manifest_file)
    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)
    first_run = dest.read_text(encoding="utf-8")

    generate_hooks_json(manifest, sample_manifest_file, dest, repo_root=tmp_path)
    second_run = dest.read_text(encoding="utf-8")

    assert first_run == second_run


def test_missing_hook_source_raises(tmp_path: Path) -> None:
    manifest_content = """
schema_version: "harness-manifest/v1"
agents: {}
hooks:
  non-existent:
    source: "harness/hooks/non_existent.py"
    runtimes:
      codex:
        hooks_json_entry: true
instructions: {}
"""
    m_file = tmp_path / "manifest.yaml"
    m_file.write_text(manifest_content.strip(), encoding="utf-8")
    manifest = load_manifest(m_file)
    dest = tmp_path / ".codex" / "hooks.json"

    with pytest.raises(FileNotFoundError):
        generate_hooks_json(manifest, m_file, dest, repo_root=tmp_path)
