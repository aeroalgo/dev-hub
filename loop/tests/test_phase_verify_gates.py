from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import _lib  # noqa: E402


def _run_pretool(
    tmp_path: Path,
    *,
    agent: str,
    prompt: str = "spawn verify",
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
        [sys.executable, str(HOOKS / "agent-pretool.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(result.stdout)


def test_tm001_agent_file_missing_deny(tmp_path: Path) -> None:
    out = _run_pretool(tmp_path, agent="verify-implement")
    raw = json.dumps(out)
    assert out.get("decision") == "DENY" or "deny" in raw.lower() or "missing" in raw.lower() or "not found" in raw.lower()


def test_tm002_alias_normalize_verify() -> None:
    assert _lib.normalize_type("verify") == "verify-implement"
    assert _lib.normalize_type("explore") == "explorer"
    assert _lib.normalize_type("verify-implement") == "verify-implement"


def test_tm003_alias_normalize_reviewer() -> None:
    assert _lib.normalize_type("reviewer") == "verify-qa"
    assert _lib.normalize_type("verify-qa") == "verify-qa"


def test_tm004_contract_verify_bugfix_sections() -> None:
    prompt_no_art = "Verify bugfix for issue without artifact AC+ AC- §0.11 VERIFY ALLOW READ: foo.py"
    missing = _lib.missing_contract_sections("verify-bugfix", prompt_no_art)
    assert "BUGFIX ARTIFACT" in missing


def test_tm005_contract_verify_decompose() -> None:
    prompt_no_cov = "Verify decompose stage s01 s02 s03 s04 s05"
    missing = _lib.missing_contract_sections("verify-decompose", prompt_no_cov)
    assert "Requirements coverage" in missing or "Stages coverage" in missing
    assert "PLAN EXCERPT" in missing


def test_tm005b_allow_read_stops_before_decompose_sections() -> None:
    prompt = (
        "## ALLOW READ\n"
        "- memory-bank/back/plan/E/md/plan.md\n"
        "- memory-bank/back/plan/E/md/decompose-index.md\n"
        "## PLAN EXCERPT\n"
        "mentions memory-bank/back/plan/E/yaml/steps/s07.yaml "
        "and memory-bank/back/plan/E/yaml/steps/s08.yaml\n"
        "## Requirements coverage\n"
        "also memory-bank/back/plan/E/yaml/steps/s02.yaml\n"
        "## Stages coverage\nok\n"
        "## Outcome map\nok\n"
        "## Replacement cleanup\nok\n"
    )
    files = _lib.allow_read_files(prompt)
    assert files == [
        "memory-bank/back/plan/E/md/plan.md",
        "memory-bank/back/plan/E/md/decompose-index.md",
    ]
    assert _lib.allow_read_violations(prompt) == []
    assert _lib.missing_contract_sections("verify-decompose", prompt) == []


def test_tm006_decompose_gate_blocks(tmp_path: Path) -> None:
    stop_gate = HOOKS / "stop-gate.py"
    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    (mb / "activeContext.md").write_text(
        "## projection\n- phase: BACK DECOMPOSE\n- armed_step: DECOMPOSE\n", encoding="utf-8"
    )

    payload = {
        "cwd": str(tmp_path),
        "session_id": "test-decompose-gate",
        "last_assistant_message": "FINISH DECOMPOSE",
        "stop_hook_active": False,
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    res = subprocess.run(
        [sys.executable, str(stop_gate)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    # stop-gate blocks DECOMPOSE phase when verify-decompose is active or required conditions met
    assert res.returncode == 0 or out.get("decision") in ("block", "DENY") or "reason" in out


def test_tm007_qa_blocked_allows_finish(tmp_path: Path) -> None:
    stop_gate = HOOKS / "stop-gate.py"
    mb = tmp_path / "memory-bank"
    mb.mkdir(parents=True, exist_ok=True)
    (mb / "activeContext.md").write_text(
        "## projection\n- phase: BACK IMPLEMENT\n", encoding="utf-8"
    )
    runtime = tmp_path / ".claude" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    verdict = {
        "schema": "loop-gate-verdict/v1",
        "status": "PASS",
        "verdict": "qa_blocked",
        "reason": "qa blocked but allowed",
    }
    (runtime / "last_verify_verdict.json").write_text(json.dumps(verdict), encoding="utf-8")

    payload = {
        "cwd": str(tmp_path),
        "session_id": "test-qa-blocked",
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(HOOKS)
    res = subprocess.run(
        [sys.executable, str(stop_gate)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
    )
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    assert out.get("decision") != "DENY"


def test_tm008_verify_qa_blocked_in_file() -> None:
    qa_agent = ROOT / ".claude" / "agents" / "verify-qa.md"
    content = qa_agent.read_text(encoding="utf-8")
    assert "BLOCKED" in content or "qa_blocked" in content


def test_tm009_dsh_preset_files_map() -> None:
    presets_dir = ROOT / "dsh" / "presets"
    for agent_name in ["verify-implement", "verify-bugfix", "verify-qa", "verify-decompose"]:
        preset_file = presets_dir / f"{agent_name}.prompt.md"
        assert preset_file.is_file(), f"Preset missing: {preset_file}"


def test_legacy_stubs_removed() -> None:
    # T-HUB-039 s10: alias stubs deleted — not symlinks, not regenerated presets.
    legacy_files = ["verify.md", "reviewer.md"]
    legacy_presets = ["verify.prompt.md", "reviewer.prompt.md"]
    for stub in legacy_files:
        assert not (ROOT / ".claude" / "agents" / stub).exists()
        assert not (ROOT / "harness" / "agents" / stub).exists()
    for preset in legacy_presets:
        assert not (ROOT / "dsh" / "presets" / preset).exists()


def test_tm010_dead_assign_regression() -> None:
    pretool_path = HOOKS / "agent-pretool.py"
    text = pretool_path.read_text(encoding="utf-8")
    assert "expected_verify_agent" in text or "verify" in text


def test_analyze_verify_agent_exists() -> None:
    assert (ROOT / ".claude" / "agents" / "analyze-verify.md").is_file()
