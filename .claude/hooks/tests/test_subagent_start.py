from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"
HOOK = HOOKS / "subagent-start.py"


def _run(tmp_path: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    event = {"session_id": "s02-test", "cwd": str(tmp_path), **payload}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _additional_context(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, result.stderr
    assert result.stdout
    output = json.loads(result.stdout)
    return output["hookSpecificOutput"]["additionalContext"]


def test_agent_type_verify_injects_contract_and_preset(tmp_path: Path) -> None:
    context = _additional_context(_run(tmp_path, {"agent_type": "verify"}))

    assert "agent_type=verify preset=preset.verify" in context
    assert "CONTRACT verify:" in context


def test_subagent_type_reviewer_is_fallback_field(tmp_path: Path) -> None:
    context = _additional_context(_run(tmp_path, {"subagent_type": "reviewer"}))

    assert "agent_type=reviewer preset=preset.reviewer" in context
    assert "CONTRACT reviewer:" in context


def test_type_explorer_is_fallback_field(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EPIC_LOOP", "1")
    context = _additional_context(_run(tmp_path, {"type": "explorer"}))

    assert "agent_type=explorer preset=preset.explorer" in context
    assert "CONTRACT explorer:" in context


def test_explore_alias_is_normalized_to_explorer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EPIC_LOOP", "1")
    context = _additional_context(_run(tmp_path, {"subagent_type": " explore "}))

    assert "agent_type=explorer preset=preset.explorer" in context
    assert "CONTRACT explorer:" in context


def test_unknown_agent_type_is_not_injected(tmp_path: Path) -> None:
    result = _run(tmp_path, {"agent_type": "unknown"})

    assert result.returncode == 0
    assert result.stdout == ""
