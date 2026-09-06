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
    session_id: str = "sess-070",
    projection_phase: str | None = None,
    armed_step: str | None = None,
) -> tuple[dict, dict]:
    """Helper to run user-prompt main() and capture state + emitted payload."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    epic_state: dict[str, object] = {
        "active": "T-HUB-070",
        "status": "running",
    }
    if projection_phase:
        epic_state["projection"] = {"phase": projection_phase}
        epic_state["phase"] = projection_phase
    if armed_step:
        epic_state["armed_step"] = armed_step

    state_file = tmp_path / ".epic" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(epic_state), encoding="utf-8")

    input_data = {
        "prompt": prompt,
        "session_id": session_id,
        "cwd": str(tmp_path),
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


@pytest.mark.xfail(
    strict=True,
    reason="s01 RED: as-built overlay forces need_verify=False and injects forbidden context",
)
def test_us001_armed_decompose_need_verify_true(monkeypatch, tmp_path: Path):
    """US-001 / SC-001 / TM-001 (TDD Red):
    When armed_step is DECOMPOSE and projection phase is DECOMPOSE:
    st['need_verify'] must be True, and additionalContext must NOT contain
    'verify/reviewer OFF' or 'promote DECOMPOSE→IMPLEMENT'.
    """
    st, emitted = _run_user_prompt(
        monkeypatch,
        tmp_path,
        prompt="BACK DECOMPOSE",
        projection_phase="BACK DECOMPOSE",
        armed_step="DECOMPOSE",
    )

    context = emitted.get("hookSpecificOutput", {}).get("additionalContext", "")

    # In s01 as-built, L164-172 forces need_verify=False and injects verify/reviewer OFF
    # This assertion will fail (red) until s02/s03 removes overlay and aligns registry.
    assert st.get("need_verify") is True, f"Expected need_verify to be True, got {st.get('need_verify')}"
    assert "verify/reviewer OFF" not in context, f"Forbidden 'verify/reviewer OFF' found in context:\n{context}"
    assert "promote DECOMPOSE→IMPLEMENT" not in context, f"Forbidden 'promote DECOMPOSE→IMPLEMENT' found in context:\n{context}"


@pytest.mark.xfail(
    strict=True,
    reason="s01 RED: as-built QA FINISH overlay injects forbidden REFLECT context",
)
def test_us002_qa_finish_no_reflect(monkeypatch, tmp_path: Path):
    """US-002 / SC-002 / TM-002 (TDD Red):
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

    # In s01 as-built, L156 injects 'Handoff → REFLECT'
    # This assertion will fail (red) until s02 removes REFLECT.
    assert "REFLECT" not in context, f"Forbidden 'REFLECT' found in context:\n{context}"
