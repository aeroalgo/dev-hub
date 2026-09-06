"""Tests for UserPromptSubmit overlay phase policy and sole-SoT behavior (T-HUB-070)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "harness" / "hooks"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import importlib.util
spec = importlib.util.spec_from_file_location("user_prompt", str(HOOKS / "user-prompt.py"))
user_prompt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(user_prompt)


def _run_user_prompt(
    monkeypatch,
    tmp_path: Path,
    prompt: str,
    session_id: str = "550e8400-e29b-41d4-a716-446655440000",
    projection_phase: str | None = None,
    armed_step: str | None = None,
) -> tuple[dict, dict]:
    """Helper to run user-prompt main() and capture state + emitted payload."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    epic_state: dict[str, object] = {
        "schema_version": "loop-state/v2",
        "active": True,
        "status": "running",
    }
    if projection_phase:
        epic_state["projection"] = {"phase": projection_phase}
        epic_state["phase"] = projection_phase
    if armed_step:
        epic_state["armed_step"] = armed_step

    from epic_paths import state_path
    state_file = state_path(tmp_path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(epic_state), encoding="utf-8")

    input_data = {
        "session_id": session_id,
        "transcript_path": str(tmp_path / "transcript.jsonl"),
        "cwd": str(tmp_path),
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
    }

    emitted: dict = {}

    def fake_read_stdin():
        return input_data

    def fake_emit(data: dict):
        nonlocal emitted
        emitted = data

    monkeypatch.setattr(user_prompt, "read_stdin", fake_read_stdin)
    monkeypatch.setattr(user_prompt, "emit", fake_emit)

    user_prompt.main()

    st = user_prompt.load_state(session_id, str(tmp_path))
    return st, emitted


def test_us001_armed_decompose_need_verify_true(monkeypatch, tmp_path: Path):
    """US-001 / SC-001 / TM-001 (TDD Green in s02/s03):
    When armed_step is DECOMPOSE and projection phase is DECOMPOSE:
    additionalContext must NOT contain 'verify/reviewer OFF' or 'promote DECOMPOSE→IMPLEMENT'.
    Real gates_from_phase('DECOMPOSE') returns need_verify=True from phase_registry.yaml.
    """
    st, emitted = _run_user_prompt(
        monkeypatch,
        tmp_path,
        prompt="BACK DECOMPOSE",
        projection_phase="BACK DECOMPOSE",
        armed_step="DECOMPOSE",
    )

    context = emitted.get("hookSpecificOutput", {}).get("additionalContext", "")

    assert st.get("need_verify") is True, f"Expected need_verify to be True, got {st.get('need_verify')}"
    assert "verify/reviewer OFF" not in context, f"Forbidden 'verify/reviewer OFF' found in context:\n{context}"
    assert "promote DECOMPOSE→IMPLEMENT" not in context, f"Forbidden 'promote DECOMPOSE→IMPLEMENT' found in context:\n{context}"



def test_us002_qa_finish_no_reflect(monkeypatch, tmp_path: Path):
    """US-002 / SC-002 / TM-002 (TDD Green in s02):
    When prompt triggers QA FINISH:
    additionalContext must NOT contain 'REFLECT' as next step.
    """
    st, emitted = _run_user_prompt(
        monkeypatch,
        tmp_path,
        prompt="BACK QA FINISH step completed",
        projection_phase="BACK QA",
        armed_step="QA",
    )

    context = emitted.get("hookSpecificOutput", {}).get("additionalContext", "")

    assert "REFLECT" not in context, f"Forbidden 'REFLECT' found in context:\n{context}"


def test_tm005_regex_qa_finish_no_reflect(monkeypatch, tmp_path: Path):
    """TM-005 / FR-006:
    When projection is not authoritative (e.g. manual/IDE session),
    regex path for QA FINISH must not inject REFLECT and must not resurrect DECOMPOSE OFF.
    """
    # Non-authoritative (no projection_phase)
    st, emitted = _run_user_prompt(
        monkeypatch,
        tmp_path,
        prompt="BACK QA FINISH step completed",
        projection_phase=None,
        armed_step=None,
    )

    context = emitted.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "REFLECT" not in context, f"Forbidden 'REFLECT' found in non-projection QA FINISH:\n{context}"
    assert "verify/reviewer OFF" not in context
    assert "promote DECOMPOSE→IMPLEMENT" not in context
