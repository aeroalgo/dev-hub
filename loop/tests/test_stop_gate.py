from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
STOP_GATE = ROOT / ".claude" / "hooks" / "stop-gate.py"
AGENT_PRETOOL = ROOT / ".claude" / "hooks" / "agent-pretool.py"
EPIC_PACKAGE = ROOT / ".claude" / "hooks" / "epic"
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load_context_loop():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec.loader.exec_module(module)
    return module


def _load_epic_lib():
    import epic

    return epic


def _write(rel: str, body: str, cwd: Path) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if rel == "memory-bank/activeContext.md" and not body.startswith("---"):
        body = (
            "---\n"
            "schema: loop-handoff/v1\n"
            "role: BACK\n"
            "mode: IMPLEMENT\n"
            "epic_id: T-HUB-057\n"
            "---\n"
            + body
        )
    path.write_text(body, encoding="utf-8")


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
        if path.is_file():
            continue
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
    if not env_path.is_file():
        env_path.write_text(
            "PROJECT_WORKFLOW_HOOKS=loop\n"
            "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
            "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n"
            "PROJECT_AGENT_EXPLORER_MODEL=fable\n",
            encoding="utf-8",
        )


def _run_stop_gate(cwd: Path, payload: dict, *, epic_loop: bool = True) -> dict:
    _ensure_gate_agents(cwd)
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_") or key in (
            "DEV_HUB",
            "HUB_ROOT",
            "PROJECT_ROOT",
            "CLAUDE_PROJECT_DIR",
        ):
            env.pop(key)
    if epic_loop:
        env["EPIC_LOOP"] = "1"
    else:
        env.pop("EPIC_LOOP", None)
    proc = subprocess.run(
        [sys.executable, str(STOP_GATE)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    if not out:
        return {}
    return json.loads(out)


def test_stop_gate_blocks_early_end_without_fingerprint_progress(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _write(
        "memory-bank/back/plan/decompose-sg/index.md",
        "| Step | Status |\n| --- | --- |\n| **s01** | pending |\n",
        tmp_path,
    )
    handoff = (
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-sg/index.md`\n\n"
        "## Handoff BACK CREATIVE — done\n"
        "- **Следующий:** BACK IMPLEMENT @s01\n"
    )
    _write("memory-bank/activeContext.md", handoff, tmp_path)
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-early-stop",
            "cwd": str(tmp_path),
            "last_assistant_message": "OK BACK IMPLEMENT — начинаю.\nМодель ИИ: GPT.",
            "stop_hook_active": False,
        },
    )
    assert result.get("decision") == "block"
    assert "epic-gate" in result.get("reason", "")
    assert "начинаю" in result.get("reason", "") or "Handoff" in result.get("reason", "")


def test_stop_gate_diagnostic_lists_missing_sections(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-diagnostic-missing-sections",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: Handoff updated.",
            "stop_hook_active": False,
        },
    )

    assert result.get("decision") == "block"
    assert "load_now" in result.get("reason", "")


def test_stop_gate_diagnostic_fingerprint_unchanged(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n## Handoff BACK\n- next\n",
        tmp_path,
    )
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-diagnostic-fingerprint",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: Handoff updated.",
            "stop_hook_active": False,
        },
    )

    assert result.get("decision") == "block"
    assert "fingerprint" in result.get("reason", "")


def test_stop_gate_allows_after_handoff_fingerprint_change(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _write(
        "memory-bank/back/plan/decompose-sg2/index.md",
        "| Step | Status |\n| --- | --- |\n| **s01** | pending |\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-sg2/index.md`\n\n"
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True

    # FINISH: rewrite handoff (fingerprint changes)
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-sg2/s01.md`\n\n"
        "## Handoff BACK IMPLEMENT s01 — done\n"
        "- **Следующий:** BACK IMPLEMENT @s02\n",
        tmp_path,
    )

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-finish-ok",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: Handoff updated.",
            "stop_hook_active": False,
        },
    )
    assert result == {}


def test_stop_gate_no_longer_requires_result_yaml(tmp_path: Path) -> None:
    """FINISH + fingerprint progress allows stop."""
    epic_lib = _load_epic_lib()
    _write(
        "memory-bank/back/plan/decompose-sg-pass/index.md",
        "| Step | Status |\n| --- | --- |\n| **s01** | pending |\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-sg-pass/index.md`\n\n"
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/qa/v1/qa-x.md`\n\n"
        "## Handoff BACK QA — pass\n"
        "- **Следующий:** BACK REFLECT\n",
        tmp_path,
    )
    allowed = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-no-result",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH.",
            "stop_hook_active": False,
        },
    )
    assert allowed == {}


def _run_agent_pretool(cwd: Path, payload: dict, *, epic_loop: bool = True) -> dict:
    _ensure_gate_agents(cwd)
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_") or key in (
            "DEV_HUB",
            "HUB_ROOT",
            "PROJECT_ROOT",
            "CLAUDE_PROJECT_DIR",
        ):
            env.pop(key)
    if epic_loop:
        env["EPIC_LOOP"] = "1"
    else:
        env.pop("EPIC_LOOP", None)
    proc = subprocess.run(
        [sys.executable, str(AGENT_PRETOOL)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    if not out:
        return {}
    return json.loads(out)


_VERIFY_STEP = (
    "memory-bank/back/implement/implement-vfy/s01-demo.yaml"
)

_VERIFY_PACKED = f"""Цель: pre-FINISH.
AC+:
- ok
AC−:
- нет
§0.11:
- ok
VERIFY:
- .venv/bin/pytest -q
ALLOW READ:
1. {_VERIFY_STEP}
2. .claude/hooks/epic_lib.py
"""


def _seed_verify_step(cwd: Path) -> None:
    _write(
        _VERIFY_STEP,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nstatus: completed\n",
        cwd,
    )


def test_agent_pretool_allows_verify_without_result_yaml(tmp_path: Path) -> None:
    """@verify allowed when activeContext + implement step exist."""
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-vfy/index.md`\n\n"
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    _write(
        "memory-bank/back/plan/decompose-vfy/index.md",
        "| Step | Status |\n| **s01** | pending |\n",
        tmp_path,
    )
    _seed_verify_step(tmp_path)

    payload = {
        "tool_name": "Agent",
        "session_id": "test-verify-no-result",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "verify",
            "prompt": _VERIFY_PACKED,
        },
    }
    allowed = _run_agent_pretool(tmp_path, payload, epic_loop=True)
    assert (
        allowed.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
    )


def test_verify_already_pass_no_reblock(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n## Handoff BACK\n- next\n",
        tmp_path,
    )
    _seed_verify_step(tmp_path)
    spawn_dir = tmp_path / ".claude" / "runtime" / "spawn-gate"
    spawn_dir.mkdir(parents=True, exist_ok=True)
    (spawn_dir / "test-verify-already-pass.json").write_text(
        json.dumps(
            {
                "need_verify": True,
                "verify_done": True,
                "verify_verdict": "PASS",
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "tool_name": "Agent",
        "session_id": "test-verify-already-pass",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "verify",
            "prompt": _VERIFY_PACKED,
        },
    }

    denied = _run_agent_pretool(tmp_path, payload, epic_loop=True)
    output = denied.get("hookSpecificOutput", {})
    assert output.get("permissionDecision") == "deny"
    assert "verify_already_pass" in output.get("permissionDecisionReason", "")

    allowed_stop = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-verify-already-pass",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: Handoff updated.",
            "stop_hook_active": False,
        },
        epic_loop=True,
    )
    assert allowed_stop == {}


def test_agent_pretool_denies_verify_when_step_missing(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n## Handoff BACK\n- next\n",
        tmp_path,
    )
    payload = {
        "tool_name": "Agent",
        "session_id": "test-verify-step-missing",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "verify",
            "prompt": _VERIFY_PACKED,
        },
    }
    out = _run_agent_pretool(tmp_path, payload, epic_loop=True)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "step_missing" in reason


def test_agent_pretool_denies_verify_without_step_in_allow(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n## Handoff BACK\n- next\n",
        tmp_path,
    )
    packed = """Цель: pre-FINISH.
AC+:
- ok
AC−:
- нет
§0.11:
- ok
VERIFY:
- .venv/bin/pytest -q
ALLOW READ:
1. .claude/hooks/epic_lib.py
"""
    payload = {
        "tool_name": "Agent",
        "session_id": "test-verify-no-step-path",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "verify",
            "prompt": packed,
        },
    }
    out = _run_agent_pretool(tmp_path, payload, epic_loop=True)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "step_not_in_allow" in reason


def test_agent_pretool_denies_verify_after_no_verdict_retries(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n## Handoff BACK\n- next\n",
        tmp_path,
    )
    _seed_verify_step(tmp_path)
    spawn_dir = tmp_path / ".claude" / "runtime" / "spawn-gate"
    spawn_dir.mkdir(parents=True, exist_ok=True)
    (spawn_dir / "test-verify-no-verdict.json").write_text(
        json.dumps(
            {
                "verify_incomplete": 1,
                "verify_no_verdict_retries": 1,
                "need_verify": True,
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "tool_name": "Agent",
        "session_id": "test-verify-no-verdict",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "verify",
            "prompt": _VERIFY_PACKED,
        },
    }
    out = _run_agent_pretool(tmp_path, payload, epic_loop=True)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "verify_no_verdict" in reason


def test_subagent_stop_increments_incomplete_without_verdict(tmp_path: Path) -> None:
    stop = ROOT / ".claude" / "hooks" / "subagent-stop.py"
    payload = {
        "agent_type": "verify",
        "session_id": "test-incomplete",
        "cwd": str(tmp_path),
        "last_assistant_message": "still reading files",
        "stop_hook_active": False,
    }
    proc = subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert proc.returncode == 2
    st = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-incomplete.json").read_text(
            encoding="utf-8"
        )
    )
    assert st.get("verify_incomplete") == 1
    assert st.get("verify_done") is False

    payload["last_assistant_message"] = (
        '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"FAIL","recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
        "BLOCKERS: x"
    )
    proc2 = subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert proc2.returncode == 0
    st2 = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-incomplete.json").read_text(
            encoding="utf-8"
        )
    )
    assert st2.get("verify_incomplete") == 0
    assert st2.get("verify_verdict") == "FAIL"
    assert st2.get("verify_done") is True


def test_subagent_stop_semantic_fail_repair_path_no_schema_retry(tmp_path: Path) -> None:
    """TM-005: valid JSON verdict FAIL + blockers emits repair hint; schema-retry count does not grow."""
    stop = ROOT / ".claude" / "hooks" / "subagent-stop.py"
    from epic.core import load_epic_state
    from _lib import get_schema_retry_count

    tool_use_id = "test-tool-semantic-fail"
    payload = {
        "agent_type": "verify",
        "session_id": "test-semantic-fail",
        "tool_use_id": tool_use_id,
        "cwd": str(tmp_path),
        "last_assistant_message": (
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
            '"verdict":"FAIL","recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
            "BLOCKERS: cp1 not done"
        ),
        "stop_hook_active": False,
    }
    proc = subprocess.run(
        [sys.executable, str(stop)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert proc.returncode == 0
    assert "@gate-repair" in proc.stderr
    assert get_schema_retry_count(tmp_path, tool_use_id) == 0


def test_stop_gate_pass_without_last_finish_tool_emits_need_human_finish_tool_missing(tmp_path: Path) -> None:
    """cp1 / TM-007 / SC-004: stop-gate after PASS without last_finish_tool emits NEED_HUMAN finish_tool_missing."""
    from epic.core import default_state, save_epic_state

    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- [s01](s01.yaml) — s01\n\n## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "last_verify_verdict": "PASS",
            "verify_done": True,
            "verify_verdict": "PASS",
            "armed_step": "s01",
        }
    )
    save_epic_state(tmp_path, st)

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-pass-no-finish-tool",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: step completed.",
            "stop_hook_active": False,
        },
    )
    assert result.get("decision") == "block"
    reason = result.get("reason", "")
    assert "NEED_HUMAN" in reason
    assert "finish_tool_missing" in reason


def test_stop_gate_schema_retry_exhausted_emits_need_human(tmp_path: Path) -> None:
    """cp2 / TM-008: schema_retry_count > N emits NEED_HUMAN schema_retry_exhausted."""
    from epic.core import default_state, save_epic_state

    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- [s01](s01.yaml) — s01\n\n## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "BACK IMPLEMENT",
            "mode": "implement",
            "schema_retry_counts": {"tool-1": 3},
        }
    )
    save_epic_state(tmp_path, st)

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-schema-exhausted",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: step completed.",
            "stop_hook_active": False,
        },
    )
    assert result.get("decision") == "block"
    reason = result.get("reason", "")
    assert "NEED_HUMAN" in reason
    assert "schema_retry_exhausted" in reason


def test_stop_gate_inactive_outside_epic_loop(tmp_path: Path) -> None:
    _write(
        "memory-bank/activeContext.md",
        "## Handoff BACK\n- hello\n",
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-no-epic",
            "cwd": str(tmp_path),
            "last_assistant_message": "OK начинаю",
            "stop_hook_active": False,
        },
        epic_loop=False,
    )
    assert result == {}


def test_stop_gate_armed_epic_ignored_without_epic_loop(tmp_path: Path) -> None:
    """IDE chat: armed state.json must not block stop / demand Handoff progress."""
    epic_lib = _load_epic_lib()
    _write(
        "memory-bank/back/plan/decompose-ide/index.md",
        "| Step | Status |\n| --- | --- |\n| **s01** | pending |\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-ide/index.md`\n\n"
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True

    early = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-ide-armed-early",
            "cwd": str(tmp_path),
            "last_assistant_message": "OK начинаю без FINISH",
            "stop_hook_active": False,
        },
        epic_loop=False,
    )
    assert early == {}

    finish = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-ide-armed-finish",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: ad-hoc done.",
            "stop_hook_active": False,
        },
        epic_loop=False,
    )
    assert finish == {}


def test_session_start_payload_requires_epic_loop(tmp_path: Path, monkeypatch) -> None:
    epic_lib = _load_epic_lib()
    _write(
        "memory-bank/back/plan/decompose-ssp/index.md",
        "| Step | Status |\n| --- | --- |\n| **s01** | pending |\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-ssp/index.md`\n\n"
        "## Handoff BACK\n- **Следующий:** BACK IMPLEMENT @s01\n",
        tmp_path,
    )
    ctx = _load_context_loop()
    prep = ctx.prepare_session(tmp_path)
    assert prep.get("ok") is True

    monkeypatch.delenv("EPIC_LOOP", raising=False)
    assert epic_lib.session_start_payload(tmp_path, source="startup") is None

    monkeypatch.setenv("EPIC_LOOP", "1")
    payload = epic_lib.session_start_payload(tmp_path, source="startup")
    assert payload is not None
    assert "Один шаг → FINISH" in payload["additionalContext"]
    assert "EPIC MODE on" not in payload["additionalContext"]
    assert payload["sessionTitle"].startswith("epic:")


BASH_PRETOOL = ROOT / ".claude" / "hooks" / "bash-pretool.py"


def _run_bash_pretool(cwd: Path, command: str, *, epic_loop: bool = True) -> dict:
    env = os.environ.copy()
    if epic_loop:
        env["EPIC_LOOP"] = "1"
    else:
        env.pop("EPIC_LOOP", None)
    proc = subprocess.run(
        [sys.executable, str(BASH_PRETOOL)],
        input=json.dumps(
            {
                "tool_name": "Bash",
                "session_id": "test-bash-pretool",
                "cwd": str(cwd),
                "tool_input": {"command": command},
            }
        ),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    if not out:
        return {}
    return json.loads(out)


def test_runner_cli_deny_reason_detects_after() -> None:
    from _lib import (
        index_bulk_status_deny_reason,
        runner_cli_deny_reason,
    )

    reason = runner_cli_deny_reason(
        "python3 .claude/hooks/epic_resolve.py after"
    )
    assert reason is not None
    assert "after" in reason
    assert runner_cli_deny_reason(
        "python3 .claude/hooks/epic_resolve.py validate-step --path x.yaml"
    ) is None
    assert runner_cli_deny_reason(
        "python3 .claude/hooks/epic_resolve.py flush-checkpoint --path x.yaml"
    ) is None
    assert runner_cli_deny_reason(
        "python3 .claude/hooks/epic_resolve.py mark-index-status "
        "--decompose decompose-v1-portal --step e13 --status completed"
    ) is None
    assert runner_cli_deny_reason("python3 .claude/hooks/epic_resolve.py status") is None
    assert runner_cli_deny_reason(
        "npm --prefix frontend exec vitest -- run src/x.test.ts"
    ) is None
    assert runner_cli_deny_reason(
        "cd frontend && npm exec vitest -- run src/x.test.ts"
    ) is None
    bulk = (
        "sed -i 's/| INTEG IMPLEMENT | pending |$/| INTEG IMPLEMENT | completed |/' "
        "memory-bank/integration/plan/decompose-v1-portal/index.md"
    )
    assert index_bulk_status_deny_reason(bulk) is not None
    assert "index_bulk_status_forbidden" in (runner_cli_deny_reason(bulk) or "")


def test_bash_pretool_denies_index_bulk_sed(tmp_path: Path) -> None:
    denied = _run_bash_pretool(
        tmp_path,
        "sed -i 's/| INTEG IMPLEMENT | pending |$/| INTEG IMPLEMENT | completed |/' "
        "memory-bank/integration/plan/decompose-v1-portal/index.md",
        epic_loop=True,
    )
    assert (
        denied.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    )
    reason = denied.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "index_bulk_status_forbidden" in reason


def test_mark_index_step_status_one_row(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    idx = (
        tmp_path
        / "memory-bank/integration/plan/decompose-demo/index.md"
    )
    idx.parent.mkdir(parents=True)
    idx.write_text(
        "**Plan ID:** demo\n\n"
        "| Step | … | Status |\n"
        "|---|---|---|\n"
        "| **e12** | [e12-a.yaml](e12-a.yaml) | INTEG IMPLEMENT | completed |\n"
        "| **e13** | [e13-b.yaml](e13-b.yaml) | INTEG IMPLEMENT | pending |\n"
        "| **e14** | [e14-c.yaml](e14-c.yaml) | INTEG IMPLEMENT | pending |\n"
        "\n"
        "## Summary-чеклист\n"
        "- [x] e12 — a\n"
        "- [ ] e13 — b\n"
        "- [ ] e14 — c\n",
        encoding="utf-8",
    )
    r = epic_lib.mark_index_step_status(
        tmp_path,
        "memory-bank/integration/plan/decompose-demo/index.md",
        "e13",
        "completed",
    )
    assert r["ok"] is True
    assert r.get("canon") == "index.yaml"
    text = idx.read_text(encoding="utf-8")
    assert "| **e13** | [e13-b.yaml](e13-b.yaml) | INTEG IMPLEMENT | completed |" in text
    assert "| **e14** | [e14-c.yaml](e14-c.yaml) | INTEG IMPLEMENT | pending |" in text
    assert "- [x] e13 — b" in text
    assert "- [ ] e14 — c" in text
    yml = (idx.parent / "index.yaml").read_text(encoding="utf-8")
    assert "id: e13" in yml
    assert "status: completed" in yml


def test_sync_index_yaml_preserves_status(tmp_path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "hooks"))
    from epic_index import sync_yaml_from_md, load_index_yaml, steps_from_doc

    idx = tmp_path / "memory-bank/integration/plan/decompose-demo/index.md"
    idx.parent.mkdir(parents=True)
    idx.write_text(
        "**Plan ID:** demo\n\n"
        "| **e01** | [e01-a.yaml](e01-a.yaml) | INTEG IMPLEMENT | pending |\n"
        "| **e02** | [e02-b.yaml](e02-b.yaml) | INTEG IMPLEMENT | pending |\n",
        encoding="utf-8",
    )
    boot = sync_yaml_from_md(idx, preserve_yaml_status=False)
    assert boot["ok"] is True
    # mutate yaml status without md
    ypath = idx.parent / "index.yaml"
    ypath.write_text(
        ypath.read_text(encoding="utf-8").replace(
            "id: e01\n  file: e01-a.yaml\n  next_phase: INTEG IMPLEMENT\n  title: e01-a\n  status: pending",
            "id: e01\n  file: e01-a.yaml\n  next_phase: INTEG IMPLEMENT\n  title: e01-a\n  status: completed",
            1,
        ),
        encoding="utf-8",
    )
    # add step in md, sync preserving yaml
    idx.write_text(
        "**Plan ID:** demo\n\n"
        "| **e01** | [e01-a.yaml](e01-a.yaml) | INTEG IMPLEMENT | pending |\n"
        "| **e02** | [e02-b.yaml](e02-b.yaml) | INTEG IMPLEMENT | pending |\n"
        "| **e03** | [e03-c.yaml](e03-c.yaml) | INTEG IMPLEMENT | pending |\n",
        encoding="utf-8",
    )
    r = sync_yaml_from_md(idx, preserve_yaml_status=True)
    assert r["ok"] is True
    steps = {s["id"]: s["status"] for s in steps_from_doc(load_index_yaml(ypath) or {})}
    assert steps["e01"] == "completed"
    assert steps["e02"] == "pending"
    assert steps["e03"] == "pending"


def test_validate_index_vs_implement_false_completed(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    dec = "memory-bank/integration/plan/decompose-demo/index.md"
    idx = tmp_path / dec
    idx.parent.mkdir(parents=True)
    idx.write_text(
        "| **e01** | a | INTEG IMPLEMENT | completed |\n"
        "| **e02** | b | INTEG IMPLEMENT | completed |\n",
        encoding="utf-8",
    )
    errs = epic_lib.validate_index_vs_implement(tmp_path, dec)
    assert errs
    assert "e01" in errs[0] or "e02" in errs[0]
    assert "finalize-step" in errs[0]


def test_bash_pretool_denies_after_in_epic_loop(tmp_path: Path) -> None:
    denied = _run_bash_pretool(
        tmp_path,
        "python3 .claude/hooks/epic_resolve.py after",
        epic_loop=True,
    )
    assert (
        denied.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    )
    reason = denied.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "runner_cli_forbidden" in reason
    assert "after" in reason


def test_bash_pretool_denies_state_projection_write(tmp_path: Path) -> None:
    out = _run_bash_pretool(
        tmp_path,
        "printf '{}' > .claude/runtime/epic/state.json",
        epic_loop=True,
    )
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "state_projection_forbidden" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_bash_pretool_allows_validate_step_in_epic_loop(tmp_path: Path) -> None:
    out = _run_bash_pretool(
        tmp_path,
        "python3 .claude/hooks/epic_resolve.py validate-step --path "
        "memory-bank/x.yaml",
        epic_loop=True,
    )
    assert out == {}


def test_bash_pretool_skips_outside_epic_loop(tmp_path: Path) -> None:
    out = _run_bash_pretool(
        tmp_path,
        "python3 .claude/hooks/epic_resolve.py after",
        epic_loop=False,
    )
    assert out == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"FAIL",'
            '"recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"PASS",'
            '"recorded_at":"2026-09-02T00:00:01Z"}\n```',
            "PASS",
        ),
        (
            'draft\n```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"PASS",'
            '"recorded_at":"2026-09-02T00:00:00Z"}\n```\nok',
            "PASS",
        ),
        (
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"PASS",'
            '"recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"FAIL",'
            '"recorded_at":"2026-09-02T00:00:01Z"}\n```',
            "FAIL",
        ),
        (
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"BLOCKED",'
            '"recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
            '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify","verdict":"PASS",'
            '"recorded_at":"2026-09-02T00:00:01Z"}\n```',
            "PASS",
        ),
        ("no verdict here", None),
    ],
)
def test_extract_verdict_last_wins(text: str, expected: str | None) -> None:
    from _lib import extract_verdict

    assert extract_verdict(text) == expected


def test_extract_verdict_contract_blob_instructional_pass_final_fail() -> None:
    """Instructional prose VERDICT must not beat final JSON fence."""
    from _lib import extract_verdict

    blob = (
        "## CONTRACT\n"
        "When done emit VERDICT: PASS on the last line.\n"
        "## Agent reply\n"
        "blocked by AC\n"
        '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"FAIL","recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
    )
    assert extract_verdict(blob) == "FAIL"


def test_extract_verdict_ignores_backtick_midline_fail_after_pass() -> None:
    """SubagentStart contract mid-line `VERDICT: FAIL` prose must not poison JSON PASS."""
    from _lib import extract_verdict

    blob = (
        "CONTRACT: первая строка = ровно `VERDICT: PASS` или `VERDICT: FAIL`.\n"
        '```json\n{"schema":"loop-gate-verdict/v1","agent_id":"verify",'
        '"verdict":"PASS","recorded_at":"2026-09-02T00:00:00Z"}\n```\n'
        "AC+: ok\n"
    )
    assert extract_verdict(blob) == "PASS"


def test_stop_gate_allows_need_human_verify_no_verdict(tmp_path: Path) -> None:
    """After no-VERDICT retries exhausted + NEED_HUMAN handoff, stop is allowed."""
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- x\n\n"
        "## Handoff INTEG IMPLEMENT — blocked\n"
        "- NEED_HUMAN: verify_no_verdict\n"
        "- **Следующий:** human retry verify\n",
        tmp_path,
    )
    spawn_dir = tmp_path / ".claude" / "runtime" / "spawn-gate"
    spawn_dir.mkdir(parents=True, exist_ok=True)
    (spawn_dir / "test-blocked-nov.json").write_text(
        json.dumps(
            {
                "need_verify": True,
                "verify_done": False,
                "verify_incomplete": 1,
                "verify_no_verdict_retries": 1,
            }
        ),
        encoding="utf-8",
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "test-blocked-nov",
            "cwd": str(tmp_path),
            "last_assistant_message": "Handoff: NEED_HUMAN: verify_no_verdict — stop",
            "stop_hook_active": False,
        },
        epic_loop=True,
    )
    assert result == {}
    st = json.loads(
        (spawn_dir / "test-blocked-nov.json").read_text(encoding="utf-8")
    )
    assert st.get("need_verify") is False
    assert st.get("verify_blocked_no_verdict") is True


def test_workflow_regexes_cover_all_roles_and_bugfix() -> None:
    from _lib import BUGFIX_RE, IMPL_RE, QA_RE

    for role in ("BACK", "FRONT", "INTEG"):
        assert IMPL_RE.search(f"{role} IMPLEMENT e01")
        assert QA_RE.search(f"{role} QA")
        assert BUGFIX_RE.search(f"{role} BUGFIX e01")

    assert IMPL_RE.search("IMPLEMENT s02")
    assert BUGFIX_RE.search("BUGFIX e03")
    assert not QA_RE.search("BACK IMPLEMENT s01")


def test_bugfix_prompt_activates_implement_gate(tmp_path: Path) -> None:
    _ensure_gate_agents(tmp_path)
    hook = ROOT / ".claude" / "hooks" / "user-prompt.py"
    payload = {
        "session_id": "test-bugfix-mode",
        "cwd": str(tmp_path),
        "prompt": "BACK BUGFIX e01 — исправить regression",
    }
    env = {**os.environ, "EPIC_LOOP": "1"}
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_"):
            env.pop(key)
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "MODE=BUGFIX" in context
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-bugfix-mode.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "implement"
    assert state["need_verify"] is True


def test_finish_rule_requires_verify_before_mark() -> None:
    rule = (
        ROOT / ".cursor" / "rules" / "shared" / "finish-block.mdc"
    ).read_text(encoding="utf-8")
    assert rule.index("@verify") < rule.index("mark-index-status")


def test_loop_runner_uses_bounded_session_wrapper() -> None:
    script = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")
    assert 'flock -n 9' in script
    assert 'SESSION_WRAPPER="$HARNESS_HOOKS/session_resilience.py"' in script
    assert '"$SESSION_WRAPPER" run-session' in script
    assert '--kill-grace "$EPIC_SESSION_KILL_GRACE_SEC"' in script
    assert 'command=("$CLAUDE" -p' in script
    assert 'command=("$CLAUDE" "$prompt"' in script


def test_loop_sh_does_not_errexit_on_nonzero_session_return() -> None:
    """Non-zero claude rc must reach record-session / transient retry.

    Bash errexit: `set -e` then `return 1` inside a function aborts the whole
    script. That skipped retry after exit_code=1 (Server error mid-response).
    """
    script = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")
    fn = script.split("run_claude_session()", 1)[1].split("\n}", 1)[0]
    assert "return \"$rc\"" in fn
    assert "set -e\n  return" not in fn
    assert "set -e\n  return \"$rc\"" not in fn
    # Live reproduction of the bash gotcha vs the fixed pattern.
    bad = subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail\n"
            "f(){ set +e; rc=1; set -e; return \"$rc\"; }\n"
            "set +e; f; echo SURVIVED=$?\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "SURVIVED=" not in bad.stdout
    assert bad.returncode != 0
    good = subprocess.run(
        [
            "bash",
            "-c",
            "set -euo pipefail\n"
            "f(){ set +e; rc=1; return \"$rc\"; }\n"
            "set +e; f; echo SURVIVED=$?\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "SURVIVED=1" in good.stdout
    assert good.returncode == 0


def _run_user_prompt(cwd: Path, prompt: str, *, epic_loop: bool = True) -> dict:
    _ensure_gate_agents(cwd)
    hook = ROOT / ".claude" / "hooks" / "user-prompt.py"
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("PROJECT_AGENT_"):
            env.pop(key)
    if epic_loop:
        env["EPIC_LOOP"] = "1"
    else:
        env.pop("EPIC_LOOP", None)
        env_path = cwd / ".claude" / "project.env"
        body = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
        if "PROJECT_WORKFLOW_HOOKS=" in body:
            lines = [
                "PROJECT_WORKFLOW_HOOKS=always"
                if line.startswith("PROJECT_WORKFLOW_HOOKS=")
                else line
                for line in body.splitlines()
            ]
            body = "\n".join(lines) + "\n"
        else:
            body = "PROJECT_WORKFLOW_HOOKS=always\n" + body
        env_path.write_text(body, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(
            {
                "session_id": "test-projection-gate",
                "cwd": str(cwd),
                "prompt": prompt,
            }
        ),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _write_agent(cwd: Path, name: str, *, default_loop: bool = True, default_chat: bool = False) -> None:
    agents = cwd / ".claude/agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / f"{name}.md").write_text(
        "---\nname: %s\noverlay:\n  managed: true\n  mode: optional\n  requires_model: false\n  default_loop: %s\n  default_chat: %s\n  verdict: none\n---\nbody\n" % (
            name,
            str(default_loop).lower(),
            str(default_chat).lower(),
        ),
        encoding="utf-8",
    )


def _policy_context(output: dict) -> str:
    return output["hookSpecificOutput"]["additionalContext"]


def _policy_active_ids(context: str) -> list[str]:
    match = re.search(r"Agent policy:.*?active=([^\n]+)", context)
    if not match:
        return []
    active_part = match.group(1)
    if ", disabled=" in active_part:
        active_part = active_part.split(", disabled=", 1)[0]
    if active_part.strip() == "none":
        return []
    return [part.strip() for part in active_part.split(",") if part.strip()]


def test_user_prompt_policy_loop_has_active_researcher_and_spawn_map(tmp_path: Path) -> None:
    _write_agent(tmp_path, "researcher")
    output = _run_user_prompt(tmp_path, "продолжить текущий шаг")
    context = _policy_context(output)
    assert "Agent policy: context=loop" in context
    assert "researcher" in _policy_active_ids(context)
    assert "researcher" in context.split("Agent policy:", 1)[0]


def test_user_prompt_policy_chat_excludes_loop_only_agent(tmp_path: Path) -> None:
    _write_agent(tmp_path, "researcher")
    output = _run_user_prompt(tmp_path, "BACK IMPLEMENT @s04", epic_loop=False)
    context = _policy_context(output)
    assert "Agent policy: context=chat" in context
    assert _policy_active_ids(context) == []
    assert "researcher" not in _policy_active_ids(context)


def test_user_prompt_policy_marks_disabled_agent_without_auto_spawn(tmp_path: Path) -> None:
    _write_agent(tmp_path, "researcher")
    _write(
        ".claude/project.env",
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n"
        "PROJECT_AGENT_REVIEWER_MODEL=sonnet\n"
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n"
        "PROJECT_AGENT_RESEARCHER_MODEL_LOOP=0\n",
        tmp_path,
    )
    output = _run_user_prompt(tmp_path, "продолжить текущий шаг")
    context = _policy_context(output)
    assert "disabled=researcher(optional)" in context
    assert "researcher" not in _policy_active_ids(context)


def _write_projection(cwd: Path, phase: str | None) -> None:
    state_path = cwd / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"phase": phase, "projection": {"phase": phase}}),
        encoding="utf-8",
    )


def test_projection_phase_arms_verify_for_front_implement(tmp_path: Path) -> None:
    _write_projection(tmp_path, "FRONT IMPLEMENT")
    _run_user_prompt(tmp_path, "продолжить текущий шаг")
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-projection-gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "implement"
    assert state["need_verify"] is True
    assert state["need_reviewer"] is False


def test_projection_phase_arms_reviewer_for_integ_qa(tmp_path: Path) -> None:
    _write_projection(tmp_path, "INTEG QA")
    _run_user_prompt(tmp_path, "продолжить текущий шаг")
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-projection-gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "qa"
    assert state["need_verify"] is False
    assert state["need_reviewer"] is True


def test_projection_phase_does_not_override_manual_regex_mode(tmp_path: Path) -> None:
    _write_projection(tmp_path, "FRONT IMPLEMENT")
    _run_user_prompt(tmp_path, "BACK QA", epic_loop=False)
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-projection-gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "qa"
    assert state["need_reviewer"] is False
    assert state["need_verify"] is False


def test_projection_phase_none_keeps_regex_fallback(tmp_path: Path) -> None:
    _write_projection(tmp_path, None)
    _run_user_prompt(tmp_path, "FRONT IMPLEMENT e01")
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/test-projection-gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["mode"] == "implement"
    assert state["need_verify"] is True


def test_gates_from_phase_ignores_terminal_phases() -> None:
    epic_lib = _load_epic_lib()
    assert epic_lib.gates_from_phase("REFLECT") == {
        "mode": None,
        "need_verify": False,
        "need_reviewer": False,
    }
    assert epic_lib.gates_from_phase("DONE") == {
        "mode": None,
        "need_verify": False,
        "need_reviewer": False,
    }


def test_timeout_abort_is_transient() -> None:
    ctx = _load_context_loop()
    assert ctx.classify_abort("timeout: sending signal TERM to command") == "transient"
    assert ctx.classify_abort("timeout: sending signal KILL to command") == "transient"
    assert ctx.classify_abort("command timed out") == "transient"


def _stale_fixture(tmp_path: Path, load_path: str, steps: str) -> None:
    _write(
        "memory-bank/back/plan/decompose-sg/index.md",
        "# Index\n",
        tmp_path,
    )
    _write(
        "memory-bank/back/plan/decompose-sg/index.yaml",
        "schema: epic-decompose-index/v1\n"
        "steps:\n"
        + steps,
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- [current] (" + load_path + ")\n\n"
        "## Handoff BACK IMPLEMENT — s03\n- done\n",
        tmp_path,
    )


def test_stop_gate_blocks_finish_without_mark_index(tmp_path: Path) -> None:
    _ensure_gate_agents(tmp_path)
    _write(
        ".claude/project.env",
        "PROJECT_WORKFLOW_HOOKS=always\nPROJECT_AGENT_VERIFY_MODEL=sonnet\n",
        tmp_path,
    )
    _write(
        "memory-bank/back/plan/decompose-sg/index.md",
        "# Index\n",
        tmp_path,
    )
    _write(
        "memory-bank/back/plan/decompose-sg/index.yaml",
        "schema: epic-decompose-index/v1\nsteps:\n"
        "- id: s01\n  file: s01-a.yaml\n  status: pending\n",
        tmp_path,
    )
    _write(
        "memory-bank/back/implement/implement-sg/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: sg\n"
        "title: a\nstatus: completed\ncheckpoints: []\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- [s02](back/plan/decompose-sg/s02-b.yaml)\n\n"
        "## Handoff BACK IMPLEMENT s01\n- **Следующий:** BACK IMPLEMENT @s02\n",
        tmp_path,
    )
    _write(
        ".claude/runtime/spawn-gate/mark-index.json",
        json.dumps({"workflow_source": "loop"}),
        tmp_path,
    )
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "status": "running",
                "mode": "implement",
                "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
                "armed_step": "s01",
                "pending_fingerprint_before": "before",
                "last_verify_verdict": "PASS",
            }
        ),
        tmp_path,
    )
    spec = importlib.util.spec_from_file_location("stop_gate_mark_index", STOP_GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    blocks: list[str] = []
    module.read_stdin = lambda: {
        "session_id": "mark-index",
        "cwd": str(tmp_path),
        "last_assistant_message": "FINISH: s01 complete",
        "stop_hook_active": False,
    }
    module.workflow_state_active = lambda *_args: True
    module.is_epic_loop_env = lambda: True
    module.load_state = lambda *_args: {}
    module.load_epic_state = lambda _cwd: {
        "active": True,
        "status": "running",
        "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
        "armed_step": "s01",
        "last_verify_verdict": "PASS",
        "last_finish_tool": {"name": "mb-finish implement", "fingerprint": "fp123"},
    }
    module.save_state = lambda *_args: None
    module.validate_finish_integrity = lambda *_args, **_kwargs: {
        "ok": False,
        "diagnostic_codes": ["mark_index_missing"],
        "errors": ["implement yaml completed but index is pending"],
    }
    module._block = blocks.append

    module.main()

    assert blocks
    assert "mark_index_missing" in blocks[0]
    assert "finalize-step" in blocks[0]


def test_stop_gate_stale_check_isolated(tmp_path: Path) -> None:
    stop_gate = importlib.util.spec_from_file_location("stop_gate", STOP_GATE)
    assert stop_gate and stop_gate.loader
    module = importlib.util.module_from_spec(stop_gate)
    stop_gate.loader.exec_module(module)

    for step_id in ("s01", "s12", "e07"):
        _stale_fixture(
            tmp_path,
            f"memory-bank/back/plan/decompose-sg/{step_id}-foo.yaml",
            f"- id: {step_id}\n  status: completed\n",
        )
        reason = module._check_stale_load_now(
            tmp_path,
            {"armed_decompose": "memory-bank/back/plan/decompose-sg/index.md"},
        )
        assert reason is not None and f"completed шаг(и): {step_id}" in reason

    _stale_fixture(
        tmp_path,
        "memory-bank/back/plan/decompose-sg/s06-foo.yaml",
        "- id: s06\n  status: pending\n",
    )
    assert module._check_stale_load_now(
        tmp_path, {"armed_decompose": "memory-bank/back/plan/decompose-sg/index.md"}
    ) is None

    _stale_fixture(
        tmp_path,
        "memory-bank/back/plan/decompose-sg/e07-baz.yaml",
        "- id: e07\n  status: done\n",
    )
    assert "completed шаг(и): e07" in module._check_stale_load_now(
        tmp_path, {"armed_decompose": "memory-bank/back/plan/decompose-sg/index.md"}
    )


def test_stop_gate_stale_load_now_blocks(tmp_path: Path) -> None:
    _stale_fixture(
        tmp_path,
        "memory-bank/back/plan/decompose-sg/s06-foo.yaml",
        "- id: s06\n  status: completed\n",
    )
    state = {
        "active": True,
        "status": "running",
        "mode": "implement",
        "pending_fingerprint_before": None,
        "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
    }
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps(state),
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "stale-block",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"
    assert "completed шаг(и): s06" in result["reason"]


def test_stop_gate_stale_load_now_pass_when_correct(tmp_path: Path) -> None:
    _stale_fixture(
        tmp_path,
        "memory-bank/back/plan/decompose-sg/s07-next.yaml",
        "- id: s06\n  status: completed\n- id: s07\n  status: pending\n",
    )
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "mode": "implement",
            "pending_fingerprint_before": None,
            "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
        }),
        tmp_path,
    )
    assert _run_stop_gate(
        tmp_path,
        {
            "session_id": "stale-pass",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    ) == {}


def test_stop_gate_stale_load_now_soft_degrade_no_yaml(tmp_path: Path) -> None:
    _write(
        "memory-bank/back/plan/decompose-sg/index.md",
        "# Index\n",
        tmp_path,
    )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- [current] (memory-bank/back/plan/decompose-sg/s06-foo.yaml)\n\n"
        "## Handoff BACK IMPLEMENT — s03\n- done\n",
        tmp_path,
    )
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "mode": "implement",
            "pending_fingerprint_before": None,
            "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
        }),
        tmp_path,
    )
    assert _run_stop_gate(
        tmp_path,
        {
            "session_id": "stale-soft",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    ) == {}


def test_stop_gate_stale_load_now_not_checked_when_not_progressed(tmp_path: Path) -> None:
    _stale_fixture(
        tmp_path,
        "memory-bank/back/plan/decompose-sg/s06-foo.yaml",
        "- id: s06\n  status: completed\n",
    )
    context = (tmp_path / "memory-bank/activeContext.md").read_text(encoding="utf-8")
    epic_lib = _load_epic_lib()
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "mode": "implement",
            "pending_fingerprint_before": epic_lib.fingerprint_context(context),
            "armed_decompose": "memory-bank/back/plan/decompose-sg/index.md",
        }),
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "stale-no-progress",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"
    assert "stale load_now" not in result["reason"]
    assert "прогресса" in result["reason"]



def _write_gate_fixture(
    cwd: Path,
    *,
    loop_enabled: str = "1",
    model: str = "sonnet",
    researcher: bool = False,
    workflow_source: str = "loop",
) -> None:
    _write(".claude/project.env", (
        f"PROJECT_WORKFLOW_HOOKS={'always' if workflow_source == 'manual' else 'loop'}\n"
        f'PROJECT_AGENT_VERIFY_MODEL="{model}"\n'
        f"PROJECT_AGENT_VERIFY_MODEL_LOOP={loop_enabled}\n"
    ), cwd)
    _write(
        ".claude/agents/verify.md",
        "---\nname: verify\n---\nverify gate\n",
        cwd,
    )
    if researcher:
        _write(
            ".claude/agents/researcher.md",
            "---\nname: researcher\noverlay:\n"
            "  managed: true\n  mode: optional\n  requires_model: false\n"
            "  default_loop: true\n  default_chat: true\n  verdict: none\n---\noptional\n",
            cwd,
        )
    _write(
        "memory-bank/activeContext.md",
        "## load_now\n- current\n\n## Handoff BACK IMPLEMENT — s05\n- next\n",
        cwd,
    )
    _write(
        ".claude/runtime/spawn-gate/gate-fixture.json",
        json.dumps({
            "workflow_source": workflow_source,
            "mode": "implement",
            "need_verify": True,
            "verify_done": False,
            "need_reviewer": False,
        }),
        cwd,
    )


def test_stop_gate_gate_bypass_chat(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path, workflow_source="manual")
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
        epic_loop=False,
    )
    assert result == {}
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/gate-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["gate_bypass_reason"] == "agent_disabled:verify"
    assert state["gate_bypassed_disabled"] == 1


def test_stop_gate_gate_bypass_explicit(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path, loop_enabled="0")
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result == {}
    state = json.loads(
        (tmp_path / ".claude/runtime/spawn-gate/gate-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["gate_bypass_reason"] == "agent_disabled:verify"
    assert state["need_verify"] is False


def test_stop_gate_gate_fail_closed(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path, model="not a model")
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"
    assert "fail-closed" in result["reason"]
    assert "model_invalid" in result["reason"]


def test_stop_gate_optional_no_gate(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path, researcher=True)
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"
    assert "обязателен @verify" in result["reason"]


def test_stop_gate_decompose_uses_validate_decompose_tree(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "phase": "DECOMPOSE",
            "armed_step": "DECOMPOSE",
        }),
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    # validate-decompose-tree is executed (or fails if executable not found in test env)
    assert result["decision"] == "block"
    assert "validate-decompose-tree" in result["reason"] or "finish-gate" in result["reason"]


def test_stop_gate_implement_uses_validate_step(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "phase": "IMPLEMENT",
            "armed_step": "s01",
        }),
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"


def test_stop_gate_unknown_gate_type_fails_closed(tmp_path: Path) -> None:
    _write_gate_fixture(tmp_path)
    _write(
        ".claude/runtime/epic/state.json",
        json.dumps({
            "active": True,
            "status": "running",
            "phase": "BOGUS_PHASE",
            "armed_step": "s01",
        }),
        tmp_path,
    )
    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "gate-fixture",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH: done",
            "stop_hook_active": False,
        },
    )
    assert result["decision"] == "block"
    assert "fail-closed" in result["reason"] or "unknown phase" in result["reason"]


def test_stop_gate_audit_accepts_qa_handoff_after_mb_finish_audit(tmp_path: Path) -> None:
    """mb-finish audit writes Handoff QA; session mode may still be audit — allow stop."""
    from epic.core import default_state, fingerprint_context, save_epic_state, write_last_finish_tool

    before = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: AUDIT\n"
        "epic_id: T-AUDIT-SG\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/audit/T-AUDIT-SG/audit-001.yaml`\n\n"
        "## Handoff BACK AUDIT\n"
        "- **Дальше:** BACK QA\n"
    )
    after = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        "epic_id: T-AUDIT-SG\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/audit/T-AUDIT-SG/audit-001.yaml`\n\n"
        "## Handoff BACK QA\n"
        "- **Дальше:** run qa phase\n"
    )
    _write("memory-bank/activeContext.md", after, tmp_path)
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "QA",
            "armed_step": "QA",
            "armed_epic": "T-AUDIT-SG",
            "pending_fingerprint_before": fingerprint_context(before),
        }
    )
    save_epic_state(tmp_path, st)
    write_last_finish_tool(
        tmp_path,
        "mb-finish audit",
        fingerprint="deadbeef",
        finished_step="AUDIT",
        armed_after_finish="QA",
    )
    _write(
        ".claude/runtime/spawn-gate/audit-qa-ok.json",
        json.dumps({"mode": "audit", "need_verify": False, "need_reviewer": False}),
        tmp_path,
    )

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "audit-qa-ok",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH AUDIT: mb-finish audit done, Handoff QA.",
            "stop_hook_active": False,
        },
    )
    assert result.get("decision") != "block", result
    assert "Handoff BACK AUDIT" not in str(result.get("reason") or "")


def test_stop_gate_audit_blocks_qa_handoff_without_finish_tool(tmp_path: Path) -> None:
    from epic.core import default_state, fingerprint_context, save_epic_state

    before = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: AUDIT\n"
        "epic_id: T-AUDIT-SG2\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/audit/T-AUDIT-SG2/audit-001.yaml`\n\n"
        "## Handoff BACK AUDIT\n"
        "- gap\n"
    )
    after = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        "epic_id: T-AUDIT-SG2\n"
        "---\n\n"
        "## load_now\n"
        "- `memory-bank/back/audit/T-AUDIT-SG2/audit-001.yaml`\n\n"
        "## Handoff BACK QA\n"
        "- **Дальше:** run qa\n"
    )
    _write("memory-bank/activeContext.md", after, tmp_path)
    st = default_state()
    st.update(
        {
            "active": True,
            "status": "running",
            "phase": "AUDIT",
            "armed_step": "AUDIT",
            "armed_epic": "T-AUDIT-SG2",
            "pending_fingerprint_before": fingerprint_context(before),
        }
    )
    save_epic_state(tmp_path, st)
    _write(
        ".claude/runtime/spawn-gate/audit-qa-block.json",
        json.dumps({"mode": "audit"}),
        tmp_path,
    )

    result = _run_stop_gate(
        tmp_path,
        {
            "session_id": "audit-qa-block",
            "cwd": str(tmp_path),
            "last_assistant_message": "FINISH AUDIT without tool",
            "stop_hook_active": False,
        },
    )
    assert result.get("decision") == "block"
    assert "mb-finish audit" in result.get("reason", "") or "Handoff BACK AUDIT" in result.get(
        "reason", ""
    )


if __name__ == "__main__":
    pass
