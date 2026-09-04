from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
PRETOOL = HOOKS / "agent-pretool.py"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load():
    spec = importlib.util.spec_from_file_location("agent_hooks_lib", HOOKS / "_lib.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent(root: Path, filename: str, frontmatter: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / filename).write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")


def _run_pretool(
    tmp_path: Path,
    *,
    agent: str,
    prompt: str = "spawn",
    session_id: str | None = None,
    **tool_input: object,
) -> dict:
    payload = {
        "tool_name": "Agent",
        "session_id": session_id or f"test-{agent}",
        "cwd": str(tmp_path),
        "tool_input": {"subagent_type": agent, "prompt": prompt, **tool_input},
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    result = subprocess.run(
        [sys.executable, str(PRETOOL)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(result.stdout)


def _gate_fence(verdict: str = "PASS", agent: str = "verify") -> str:
    return (
        f"```json\n"
        f'{{"schema":"loop-gate-verdict/v1","agent_id":"{agent}",'
        f'"verdict":"{verdict}","recorded_at":"2026-08-31T12:00:00Z"}}\n'
        f"```\n"
    )


def _run_subagent_stop(
    tmp_path: Path,
    *,
    agent: str,
    session_id: str,
    message: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if message is None:
        message = _gate_fence("PASS", agent) + "ok"
    payload = {
        "agent_type": agent,
        "session_id": session_id,
        "cwd": str(tmp_path),
        "last_assistant_message": message,
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    return subprocess.run(
        [sys.executable, str(HOOKS / "subagent-stop.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )


def test_registry_active_agents_respects_context_scope(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(tmp_path, "researcher.md", "name: researcher\noverlay:\n  managed: true\n  requires_model: true\n  default_loop: true")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert lib.registry_active_agents("loop", tmp_path) == {"researcher": "sonnet"}
    assert lib.registry_active_agents("chat", tmp_path) == {}


def test_active_overlay_contains_protocol(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(tmp_path, "verify.md", "name: verify")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert "verify" in lib.active_overlay(tmp_path)


def test_negative_invalid_selector_does_not_enable_agent(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n"
        "PROJECT_AGENT_RESEARCHER_MODEL_LOOP=maybe\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert lib.registry_active_agents("loop", tmp_path) == {}


def test_negative_invalid_model_does_not_enable_agent(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=not a model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert lib.registry_active_agents("loop", tmp_path) == {}


def test_negative_optional_agent_does_not_promote_gate(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  default_chat: true\n  requires_model: false",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    spawn_map = lib.build_spawn_map(tmp_path)

    assert "Optional agent | @researcher доступен по вызову parent, не блокирует completion |" in spawn_map
    assert "Gate agent | @researcher" not in spawn_map


def test_negative_loop_scope_requires_epic_loop_env(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  default_chat: false\n  requires_model: false",
    )
    monkeypatch.delenv("EPIC_LOOP", raising=False)

    output = _run_pretool(tmp_path, agent="researcher")
    hook = output["hookSpecificOutput"]

    assert hook["permissionDecision"] == "deny"
    assert "scope_disabled (context=chat)" in hook["permissionDecisionReason"]


def test_new_agent_no_const(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(tmp_path, "researcher.md", "name: researcher\noverlay:\n  managed: true\n  requires_model: true\n  default_loop: true")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    assert "researcher" not in lib.AGENT_MODEL_ENV_KEYS
    assert lib.agent_enabled("researcher", tmp_path) is True


def test_managed_agent_model_comes_from_registry(tmp_path: Path) -> None:
    lib = _load()
    _agent(tmp_path, "researcher.md", "name: researcher")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=openai/gpt-4.1\n", encoding="utf-8"
    )

    assert lib.agent_model_from_project_env("researcher", tmp_path) == "openai/gpt-4.1"


def test_spawn_map_legacy_agents_preserves_text(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(tmp_path, "verify.md", "name: verify")
    _agent(tmp_path, "reviewer.md", "name: reviewer")
    _agent(tmp_path, "explorer.md", "name: explorer")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
        "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n"
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    spawn_map = lib.build_spawn_map(tmp_path)

    assert "Overlay: @explorer · @verify · @reviewer" in spawn_map
    assert "@explorer ОБЯЗАТЕЛЬНО" in spawn_map
    assert "@verify" in spawn_map
    assert "@reviewer" in spawn_map


def test_spawn_map_optional_agent_is_non_blocking(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    spawn_map = lib.build_spawn_map(tmp_path)

    assert "Optional agent | @researcher доступен по вызову parent, не блокирует completion |" in spawn_map


def test_spawn_map_chat_excludes_loop_only_agents(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.delenv("EPIC_LOOP", raising=False)

    spawn_map = lib.build_spawn_map(tmp_path)

    assert "@researcher" not in spawn_map
    assert "managed search agent недоступен" in spawn_map


def test_spawn_map_empty_registry_is_safe(tmp_path: Path, monkeypatch) -> None:
    lib = _load()
    monkeypatch.setenv("EPIC_LOOP", "1")

    spawn_map = lib.build_spawn_map(tmp_path)

    assert "Overlay: (нет managed agents)" in spawn_map


def test_pretool_deny_scope(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: false\n  default_chat: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    output = _run_pretool(tmp_path, agent="researcher")
    hook = output["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert "scope_disabled" in hook["permissionDecisionReason"]
    assert "context=loop" in hook["permissionDecisionReason"]


def test_pretool_pin_override(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_RESEARCHER_MODEL=sonnet\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    output = _run_pretool(tmp_path, agent="researcher", model="opus")
    hook = output["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert hook["updatedInput"]["model"] == "sonnet"


def test_pretool_non_managed_free(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EPIC_LOOP", "1")

    output = _run_pretool(tmp_path, agent="general-purpose")
    hook = output["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert "HARD RULE" in hook["updatedInput"]["prompt"]


def test_pretool_worktree_strip(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "researcher.md",
        "name: researcher\noverlay:\n  managed: true\n  mode: optional\n  default_loop: true\n  requires_model: false\n  allow_worktree: false",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    output = _run_pretool(tmp_path, agent="researcher", isolation="worktree")
    hook = output["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert "isolation" not in hook["updatedInput"]
    assert "HARD RULE" in hook["updatedInput"]["prompt"]


def _seed_verify_files(tmp_path: Path) -> str:
    step = (
        "memory-bank/back/implement/implement-T-test/s01-demo.yaml"
    )
    step_path = tmp_path / step
    step_path.parent.mkdir(parents=True, exist_ok=True)
    step_path.write_text("status: completed\n", encoding="utf-8")
    ac = tmp_path / "memory-bank" / "activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text("## load_now\n- x\n## Handoff\nok\n", encoding="utf-8")
    return step


def _verify_prompt(step: str) -> str:
    return (
        "Цель\nAC+\n- a\nAC−\n- b\n§0.11\n- c\nVERIFY\n"
        "timeout 300s .venv/bin/pytest -q\nALLOW READ\n"
        f"{step}\n"
        "memory-bank/activeContext.md\n"
    )


def _verify_prompt_markdown_headings(step: str) -> str:
    return (
        "Цель\n# AC+\n- a\n# AC-\n- b\n# 0.11\n- c\n# VERIFY\n"
        "timeout 300s .venv/bin/pytest -q\n# ALLOW READ\n"
        f"{step}\n"
        "memory-bank/activeContext.md\n"
    )


def test_missing_contract_sections_accepts_markdown_and_ascii_minus() -> None:
    lib = _load()
    prompt = (
        "# AC+\n- a\n# AC-\n- b\n# 0.11\n- c\n# VERIFY\n"
        "pytest -q\n# ALLOW READ\nfoo.py\n"
    )
    assert lib.missing_contract_sections("verify", prompt) == []
    assert lib.allow_read_files(prompt) == ["foo.py"]


def test_pretool_allow_verify_markdown_headings(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")
    step = _seed_verify_files(tmp_path)
    out = _run_pretool(
        tmp_path,
        agent="verify",
        prompt=_verify_prompt_markdown_headings(step),
    )
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_pretool_deny_parallel_managed(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "explorer.md",
        "name: explorer\noverlay:\n  managed: true\n  mode: search\n  default_loop: true\n  requires_model: true",
    )
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n"
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")
    sid = "sess-parallel-managed"
    step = _seed_verify_files(tmp_path)

    first = _run_pretool(tmp_path, agent="explorer", session_id=sid)
    assert first["hookSpecificOutput"]["permissionDecision"] == "allow"

    second = _run_pretool(
        tmp_path,
        agent="verify",
        session_id=sid,
        prompt=_verify_prompt(step),
    )
    hook = second["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert "managed_in_flight" in hook["permissionDecisionReason"]

    stop = _run_subagent_stop(tmp_path, agent="explorer", session_id=sid, message="done")
    assert stop.returncode == 0

    retry = _run_pretool(
        tmp_path,
        agent="verify",
        session_id=sid,
        prompt=_verify_prompt(step),
    )
    assert retry["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_pretool_deny_same_model_inflight(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    _agent(
        tmp_path,
        "reviewer.md",
        "name: reviewer\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-blocked-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
        "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")
    sid = "sess-same-model"
    step = _seed_verify_files(tmp_path)

    first = _run_pretool(
        tmp_path,
        agent="verify",
        session_id=sid,
        prompt=_verify_prompt(step),
    )
    assert first["hookSpecificOutput"]["permissionDecision"] == "allow"

    second = _run_pretool(
        tmp_path,
        agent="reviewer",
        session_id=sid,
        prompt=(
            "Suite results\nok\nAC+\n- a\nAC−\n- b\n§0.11\n- c\nALLOW READ\n"
            f"{step}\n"
            "memory-bank/activeContext.md\n"
        ),
    )
    hook = second["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert "managed_in_flight" in hook["permissionDecisionReason"]
    assert "model_in_flight" in hook["permissionDecisionReason"]
    assert "sonnet" in hook["permissionDecisionReason"]



def _run_subagent_start(
    tmp_path: Path,
    *,
    agent: str,
    session_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = {
        "agent_type": agent,
        "session_id": session_id or f"start-{agent}",
        "cwd": str(tmp_path),
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    return subprocess.run(
        [sys.executable, str(HOOKS / "subagent-start.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )


def _run_posttool(
    tmp_path: Path,
    *,
    agent: str,
    session_id: str,
    message: str,
    tool_use_id: str,
) -> subprocess.CompletedProcess[str]:
    payload = {
        "tool_name": "Agent",
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_use_id": tool_use_id,
        "tool_input": {"subagent_type": agent, "prompt": "verify"},
        "tool_response": {"content": [{"type": "text", "text": message}]},
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    env["EPIC_LOOP"] = "1"
    return subprocess.run(
        [sys.executable, str(HOOKS / "agent-posttool.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )


def test_posttool_fail_then_pass_mirrors_epic_last_verify(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: coarse session:verify dedupe must not swallow FAIL→PASS."""
    lib = _load()
    monkeypatch.setenv("EPIC_LOOP", "1")
    _agent(tmp_path, "verify.md", "name: verify")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_WORKFLOW_HOOKS=loop\nPROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    sid = "claude-parent-sess"
    identity = {
        "session_id": "runner-epic-sess",
        "epic_id": "T-004",
        "role": "BACK",
        "step": "s05",
        "projection_hash": "hash-1",
        "phase_epoch": "epoch-1",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    epic_dir = tmp_path / ".claude" / "runtime" / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    epic_state = {
        "active": True,
        "session_id": identity["session_id"],
        "armed_epic": "T-004",
        "armed_step": "s05",
        "role": "BACK",
        "projection_hash": identity["projection_hash"],
        "phase_epoch": identity["phase_epoch"],
        "event_digest": identity["event_digest"],
        "projection": {
            "epic_id": "T-004",
            "role": "BACK",
            "next_step": "s05",
            "projection_hash": identity["projection_hash"],
            "phase_epoch": identity["phase_epoch"],
            "event_digest": identity["event_digest"],
        },
        "last_verify_verdict": None,
        "last_verify_evidence": None,
    }
    (epic_dir / "state.json").write_text(
        json.dumps(epic_state) + "\n", encoding="utf-8"
    )
    gate = {
        "mode": "implement",
        "need_verify": True,
        "workflow_source": "loop",
        "verify_done": False,
        "verify_verdict": None,
        "gate_identity": identity,
        "verdict_recorded_agents": [],
    }
    lib.save_state(sid, str(tmp_path), gate)

    fail = _run_posttool(
        tmp_path,
        agent="verify",
        session_id=sid,
        tool_use_id="call_fail",
        message=_gate_fence("FAIL") + "AC+: status=in_progress\n",
    )
    assert fail.returncode == 0, fail.stderr
    after_fail = json.loads((epic_dir / "state.json").read_text(encoding="utf-8"))
    assert after_fail["last_verify_verdict"] == "FAIL"
    parent_fail = lib.load_state(sid, str(tmp_path))
    assert parent_fail["verify_verdict"] == "FAIL"

    # Legacy coarse key from the bug — must not block PASS with new tool_use_id.
    parent_fail["verdict_recorded_agents"] = [f"{sid}:verify"]
    lib.save_state(sid, str(tmp_path), parent_fail)

    ok = _run_posttool(
        tmp_path,
        agent="verify",
        session_id=sid,
        tool_use_id="call_pass",
        message=_gate_fence("PASS") + "AC+: all good\n",
    )
    assert ok.returncode == 0, ok.stderr
    after_pass = json.loads((epic_dir / "state.json").read_text(encoding="utf-8"))
    assert after_pass["last_verify_verdict"] == "PASS"
    parent_pass = lib.load_state(sid, str(tmp_path))
    assert parent_pass["verify_verdict"] == "PASS"
    assert parent_pass["verify_evidence"]["verdict"] == "PASS"


def test_settings_no_per_agent_matcher(tmp_path: Path) -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    start = settings["hooks"]["SubagentStart"]
    stop = settings["hooks"]["SubagentStop"]
    assert set(entry["matcher"] for entry in start) == {".*"}
    assert set(entry["matcher"] for entry in stop) == {".*"}

    result = _run_subagent_start(tmp_path, agent="researcher")
    assert result.returncode == 0
    assert result.stdout == ""


def test_subagent_lifecycle_legacy_agents(tmp_path: Path) -> None:
    for agent in ("verify", "reviewer", "explorer"):
        started = _run_subagent_start(tmp_path, agent=agent)
        assert started.returncode == 0
        if agent == "explorer":
            assert "SubagentStart" in started.stdout
        else:
            assert "SubagentStart" in started.stdout

        stopped = _run_subagent_stop(
            tmp_path,
            agent=agent,
            session_id=f"stop-{agent}",
            message=_gate_fence("PASS", agent) if agent in {"verify", "reviewer"} else "done",
        )
        assert stopped.returncode == 0

def test_normalize_type_alias_explore() -> None:
    lib = _load()
    assert lib.normalize_type("explore") == "explorer"
    assert lib.normalize_type("explorer") == "explorer"
    assert lib.normalize_type(None) is None


def test_pretool_alias_explore_normalizes_to_explorer(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "explorer.md",
        "name: explorer\noverlay:\n  managed: true\n  mode: search\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EPIC_LOOP", "1")
    # Isolate spawn-gate state from hub (product_cwd/DEV_HUB remap)
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)
    monkeypatch.delenv("HUB_ROOT", raising=False)
    out = _run_pretool(tmp_path, agent="explore", session_id="sess-alias-explore")
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow", hook.get("permissionDecisionReason")
    assert hook["updatedInput"]["subagent_type"] == "explorer"


def test_posttool_mirror_error_logs_stderr_and_saves_state(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-9: mirror failure must be visible on stderr; spawn-state still saved."""
    lib = _load()
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)
    monkeypatch.delenv("HUB_ROOT", raising=False)
    _agent(tmp_path, "verify.md", "name: verify")
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_WORKFLOW_HOOKS=loop\nPROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        encoding="utf-8",
    )
    sid = "sess-mirror-err"
    identity = {
        "session_id": "runner-sess",
        "epic_id": "T-004",
        "role": "BACK",
        "step": "s06",
        "projection_hash": "h1",
        "phase_epoch": "e1",
        "event_digest": "d1",
        "authority": "autonomous",
    }
    epic_dir = tmp_path / ".claude" / "runtime" / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    (epic_dir / "state.json").write_text(
        json.dumps(
            {
                "active": True,
                "session_id": identity["session_id"],
                "armed_epic": "T-004",
                "armed_step": "s06",
                "role": "BACK",
                "projection_hash": "h1",
                "phase_epoch": "e1",
                "event_digest": "d1",
                "projection": {
                    "epic_id": "T-004",
                    "role": "BACK",
                    "next_step": "s06",
                    "projection_hash": "h1",
                    "phase_epoch": "e1",
                    "event_digest": "d1",
                },
                "last_verify_verdict": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    lib.save_state(
        sid,
        str(tmp_path),
        {
            "mode": "implement",
            "need_verify": True,
            "workflow_source": "loop",
            "verify_done": False,
            "verify_verdict": None,
            "gate_identity": identity,
            "verdict_recorded_agents": [],
        },
    )

    # Make epic state unwritable so mirror_verify_verdict raises OSError on save.
    os.chmod(epic_dir, 0o555)
    payload = {
        "tool_name": "Agent",
        "session_id": sid,
        "cwd": str(tmp_path),
        "tool_use_id": "call_boom",
        "tool_input": {"subagent_type": "verify", "prompt": "verify"},
        "tool_response": {
            "content": [{"type": "text", "text": _gate_fence("PASS") + "ok"}]
        },
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    env["EPIC_LOOP"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, str(HOOKS / "agent-posttool.py")],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
        )
    finally:
        os.chmod(epic_dir, 0o755)
    assert result.returncode == 0, result.stderr
    assert "mirror" in result.stderr.lower() and "failed" in result.stderr.lower(), result.stderr
    st = lib.load_state(sid, str(tmp_path))
    assert st.get("verify_verdict") == "PASS"
    assert st.get("verify_done") is True


def test_save_state_concurrent_does_not_lose_update(tmp_path: Path, monkeypatch) -> None:
    """FR-10: concurrent save_state must not leave truncated/lost JSON."""
    import concurrent.futures

    lib = _load()
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)
    monkeypatch.delenv("HUB_ROOT", raising=False)
    sid = "sess-concurrent"
    cwd = str(tmp_path)

    def _write(i: int) -> None:
        st = lib.load_state(sid, cwd)
        st["spawn_allowed"] = i
        st["marker"] = f"v{i}"
        lib.save_state(sid, cwd, st)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_write, range(40)))

    path = lib.state_path(sid, cwd)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)  # must be valid JSON (no truncated write)
    assert "spawn_allowed" in data
    assert "marker" in data
