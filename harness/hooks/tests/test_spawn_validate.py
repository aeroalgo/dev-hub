from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from spawn_validate import validate_spawn_input  # noqa: E402


def _agent(root: Path, filename: str, frontmatter: str) -> None:
    agents = root / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / filename).write_text(
        f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8"
    )


def _verify_setup(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "verify.md",
        "name: verify\noverlay:\n  managed: true\n  mode: gate\n  default_loop: true\n  requires_model: true\n  verdict: pass-fail",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_VERIFY_MODEL=sonnet\n", encoding="utf-8"
    )


def _verify_prompt(allow_read: str = "foo.py") -> str:
    return (
        "AC+\n- satisfied\nAC-\n- none\n§0.11\n- checked\n"
        "VERIFY\n- checked\nALLOW READ\n"
        f"{allow_read}\n"
    )


def test_missing_contract_sections_are_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "verify", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete" in reason for reason in deny_reasons)


def test_allow_read_directory_is_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "verify", "prompt": _verify_prompt("memory-bank/")}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("ALLOW READ" in reason and "каталог" in reason for reason in deny_reasons)


def test_managed_in_flight_is_denied(tmp_path: Path, monkeypatch) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    state = {
        "in_flight": [
            {"agent": "explorer", "model": "fable", "managed": True}
        ]
    }
    tool_input = {"subagent_type": "verify", "prompt": _verify_prompt()}
    deny_reasons, _notes = validate_spawn_input(tool_input, state, tmp_path)

    assert any("managed_in_flight" in reason for reason in deny_reasons)


def test_well_formed_prompt_without_in_flight_is_allowed(
    tmp_path: Path, monkeypatch
) -> None:
    _verify_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "verify", "prompt": _verify_prompt()}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []


def test_alias_is_normalized_by_spawn_validation(tmp_path: Path, monkeypatch) -> None:
    _agent(
        tmp_path,
        "explorer.md",
        "name: explorer\noverlay:\n  managed: true\n  mode: search\n  default_loop: true\n  requires_model: true",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_EXPLORER_MODEL=fable\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "explore", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []
    assert tool_input["subagent_type"] == "explorer"


def test_cli_round_trip_denies_incomplete_spawn() -> None:
    payload = {
        "tool_name": "Agent",
        "tool_input": {"subagent_type": "verify-implement", "prompt": "spawn"},
        "session_id": "s03-round-trip",
        "cwd": str(ROOT),
    }
    env = {**dict(__import__("os").environ), "EPIC_LOOP": "1", "PYTHONPATH": str(HOOKS)}
    completed = subprocess.run(
        [sys.executable, str(HOOKS / "spawn_validate.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    result = json.loads(completed.stdout)
    assert any("prompt_incomplete" in reason for reason in result["deny_reasons"])


def _repair_setup(tmp_path: Path) -> None:
    _agent(
        tmp_path,
        "gate-repair.md",
        "name: gate-repair\noverlay:\n  managed: true\n  mode: repair\n  default_loop: true\n  requires_model: true\n  verdict: none",
    )
    (tmp_path / ".claude" / "project.env").write_text(
        "PROJECT_AGENT_GATE_REPAIR_MODEL=sonnet\n", encoding="utf-8"
    )


def _repair_prompt() -> str:
    return (
        "BLOCKERS\n- diagnostic_code_mismatch\nALLOW WRITE\n"
        "loop/mb_finish/finish_implement.py\n"
        "VERIFY\n"
        "timeout 300s .venv/bin/pytest harness/hooks/tests/test_mb_finish_implement.py -q\n"
    )


def test_gate_repair_missing_sections_denied(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "gate-repair", "prompt": "spawn"}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert any("prompt_incomplete" in reason for reason in deny_reasons)


def test_gate_repair_well_formed_prompt_allowed(tmp_path: Path, monkeypatch) -> None:
    _repair_setup(tmp_path)
    monkeypatch.setenv("EPIC_LOOP", "1")

    tool_input = {"subagent_type": "gate-repair", "prompt": _repair_prompt()}
    deny_reasons, _notes = validate_spawn_input(tool_input, {}, tmp_path)

    assert deny_reasons == []
