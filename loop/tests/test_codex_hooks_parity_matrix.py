import pytest
from loop.runtime_materializers.hooks_json import EVENT_MAPPING, CODEX_MIN_VERSION

FR_002_REQUIRED_EVENTS = {
    "Stop",
    "SubagentStop",
    "PreToolUse",
    "UserPromptSubmit",
    "SessionStart",
    "SubagentStart",
    "PostToolUse:agent",
    "PostToolUse:bash",
}


def test_event_mapping_covers_fr002_events():
    mapped_events = set(EVENT_MAPPING.values())
    missing = FR_002_REQUIRED_EVENTS - mapped_events
    assert not missing, f"EVENT_MAPPING is missing required FR-002 events: {missing}"


def test_codex_min_version_defined():
    assert CODEX_MIN_VERSION
    assert isinstance(CODEX_MIN_VERSION, str)


def test_generated_hooks_json_has_all_fr002_events_and_timeouts(tmp_path):
    from loop.runtime_materializers.manifest_schema import load_manifest
    from loop.runtime_materializers.hooks_json import generate_hooks_json
    from pathlib import Path
    import json

    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "harness" / "manifest.yaml"
    manifest = load_manifest(manifest_path)

    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, manifest_path, dest, repo_root=repo_root)

    data = json.loads(dest.read_text(encoding="utf-8"))
    hooks = data.get("hooks", {})

    # cp1: check all required event keys
    required_events = {"Stop", "SubagentStop", "PreToolUse", "PostToolUse", "UserPromptSubmit", "SessionStart", "SubagentStart"}
    assert required_events.issubset(set(hooks.keys()))

    # cp2: check PostToolUse has Bash entry with timeout_ms >= 45000
    post_tool_entries = hooks.get("PostToolUse", [])
    assert len(post_tool_entries) >= 2
    bash_entries = [e for e in post_tool_entries if e.get("matcher", "").lower() in ("bash", "shell")]
    assert len(bash_entries) == 1
    assert bash_entries[0].get("timeout_ms", 0) >= 45000
    assert "bash-output-cap.py" in bash_entries[0].get("command", "")

    agent_entries = [e for e in post_tool_entries if "agent" in e.get("matcher", "").lower()]
    assert len(agent_entries) == 1
    assert "agent-posttool.py" in agent_entries[0].get("command", "")

