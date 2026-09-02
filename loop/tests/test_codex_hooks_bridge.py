"""Integration tests verifying stop-gate and spawn-gate hooks bridge with Codex runtime semantics.

AC- #2: No separate spawn policy for codex.
US-003: Semantics unchanged across runtimes.
Outcome: SC-004, TM-004.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest


def _ensure_gate_agents(cwd: Path) -> None:
    agents = cwd / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    specs = (
        ("verify", "gate", "pass-fail", True),
        ("reviewer", "gate", "pass-blocked-fail", True),
        ("explorer", "search", "none", False),
    )
    for name, mode, verdict, requires_model in specs:
        path = agents / f"{name}.md"
        path.write_text(
            "---\n"
            f"name: {name}\n"
            "overlay:\n"
            "  managed: true\n"
            f"  mode: {mode}\n"
            f"  requires_model: {str(requires_model).lower()}\n"
            "  default_loop: true\n"
            "  default_chat: false\n"
            f"  verdict: {verdict}\n"
            "  allow_worktree: false\n"
            "---\nbody\n",
            encoding="utf-8",
        )
    env_path = cwd / ".claude" / "project.env"
    env_path.write_text(
        "PROJECT_WORKFLOW_HOOKS=loop\n"
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
        "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n"
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n",
        encoding="utf-8",
    )


def test_stop_gate_deny_codex_without_verify(tmp_path: Path) -> None:
    """Simulate codex session FINISH without verify PASS -> stop-gate denies (same verdict as claude)."""
    stop_gate_script = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "stop-gate.py"
    assert stop_gate_script.exists()

    _ensure_gate_agents(tmp_path)

    state_file = tmp_path / ".claude" / "state" / "test-codex-session.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({
            "mode": "IMPLEMENT",
            "workflow_source": "loop",
            "need_verify": True,
            "verify_done": False,
            "active": True,
            "session_id": "test-codex-session",
        }),
        encoding="utf-8"
    )

    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_") or key in (
            "DEV_HUB",
            "HUB_ROOT",
            "PROJECT_ROOT",
            "CLAUDE_PROJECT_DIR",
        ):
            env.pop(key)

    env["RUNTIME_ID"] = "codex"
    env["EPIC_LOOP"] = "1"

    payload = {
        "session_id": "test-codex-session",
        "cwd": str(tmp_path),
        "last_assistant_message": "FINISH\nМодель ИИ: Codex.",
        "stop_hook_active": False,
    }

    res = subprocess.run(
        [sys.executable, str(stop_gate_script)],
        input=json.dumps(payload),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, f"stderr: {res.stderr}, stdout: {res.stdout}"
    assert res.stdout, f"Expected stdout block JSON, got empty string. stderr: {res.stderr}"
    data = json.loads(res.stdout)
    assert data.get("decision") == "block"
    assert "verify" in data.get("reason", "") or "spawn-gate" in data.get("reason", "") or "finish-gate" in data.get("reason", "") or "epic-gate" in data.get("reason", "")


def test_spawn_gate_parity_codex_uses_spawn_hard(tmp_path: Path) -> None:
    """Spawn-gate policy for codex == claude (no extra/separate rules AC- #2)."""
    spawn_validate_script = Path(__file__).resolve().parents[2] / "harness" / "hooks" / "spawn_validate.py"
    assert spawn_validate_script.exists()

    input_payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "verify-implement",
            "prompt": "Test verify prompt",
            "runtime_id": "codex",
        },
        "session_id": "test-session",
        "cwd": str(tmp_path),
    }

    res = subprocess.run(
        [sys.executable, str(spawn_validate_script)],
        input=json.dumps(input_payload),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, f"stderr: {res.stderr}"
    data = json.loads(res.stdout)
    assert "deny_reasons" in data


def test_hooks_json_stop_event_wired(tmp_path: Path) -> None:
    """.codex/hooks.json contains Stop event pointing to stop-gate entrypoint."""
    from loop.runtime_materializers.hooks_json import generate_hooks_json, GENERATED_HEADER
    from loop.runtime_materializers.manifest_schema import load_manifest

    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "harness" / "manifest.yaml"
    manifest = load_manifest(manifest_path)

    dest = tmp_path / ".codex" / "hooks.json"
    generate_hooks_json(manifest, manifest_path, dest, repo_root=repo_root)

    content = dest.read_text(encoding="utf-8")
    data = json.loads(content)
    meta = json.loads((tmp_path / ".codex" / "hooks.meta.json").read_text(encoding="utf-8"))
    assert GENERATED_HEADER in meta["header"]
    assert "_meta" not in data

    assert "hooks" in data
    hooks = data["hooks"]
    assert "Stop" in hooks
    assert any("harness/hooks/stop-gate.py" in str(item.get("command", "")) for item in hooks["Stop"])
    assert "SubagentStop" in hooks
    assert any(
        "harness/hooks/subagent-stop.py" in str(item.get("command", ""))
        for item in hooks["SubagentStop"]
    )
    assert "PreToolUse" in hooks
    assert any(
        "harness/hooks/agent-pretool.py" in str(item.get("command", ""))
        for item in hooks["PreToolUse"]
    )


def test_agent_registry_discovers_harness_agents_without_claude_copy(tmp_path: Path) -> None:
    """gate-repair and other harness agents resolve when .claude/agents is empty."""
    harness_agents = tmp_path / "harness" / "agents"
    harness_agents.mkdir(parents=True)
    (harness_agents / "gate-repair.md").write_text(
        "---\n"
        "name: gate-repair\n"
        "description: repair\n"
        "overlay:\n"
        "  managed: true\n"
        "  mode: repair\n"
        "  requires_model: true\n"
        "  default_loop: true\n"
        "  default_chat: false\n"
        "  verdict: none\n"
        "  allow_worktree: false\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness" / "hooks"))
    from agent_registry import discover_registry

    reg = discover_registry(tmp_path)
    assert reg.get("gate-repair") is not None
