from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
WRITE_PRETOOL = HOOKS / "write-pretool.py"


def _load_lib():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("project_lib_ac_lock", HOOKS / "_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _owner(lib, pid: int, epic_id: str = "T-HUB-049", phase: str = "QA", step: str = "QA"):
    return lib.RunnerOwner(
        pid=pid,
        host="runner-host",
        started_at="2026-09-04T12:00:00Z",
        session_id="session-lock",
        selected_identity="BACK QA",
        mode="qa",
        model="claude-sonnet",
        timeout_config={"session_timeout_sec": 3600, "kill_grace_sec": 30},
        epic_id=epic_id,
        phase=phase,
        step=step,
    )


def _write_live_owner(tmp_path: Path, lib, pid: int | None = None, **kwargs):
    runtime = tmp_path / "runtime" / tmp_path.name / "epic"
    runtime.mkdir(parents=True, exist_ok=True)
    lib.write_runner_owner(runtime / "runner.json", _owner(lib, pid or os.getpid(), **kwargs))
    return runtime


def test_chat_cannot_overwrite_live_loop_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("EPIC_LOOP", raising=False)
    _write_live_owner(tmp_path, lib)

    reason = lib.runner_owns_active_context_reason(
        tmp_path, epic_id="T-HUB-061", phase="PLAN", same_session=False
    )
    assert reason is not None
    assert "runner_owns_active_context" in reason
    with pytest.raises(lib.ActiveContextLocked):
        lib.assert_active_context_writable(
            tmp_path, epic_id="T-HUB-061", phase="PLAN", same_session=False
        )


def test_loop_same_epic_may_advance_phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("EPIC_LOOP", "1")
    _write_live_owner(tmp_path, lib, epic_id="T-HUB-049", phase="QA")

    assert (
        lib.runner_owns_active_context_reason(
            tmp_path, epic_id="T-HUB-049", phase="DONE", same_session=True
        )
        is None
    )


def test_stale_owner_does_not_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    _write_live_owner(tmp_path, lib, pid=999_999_999, epic_id="T-HUB-049")

    assert lib.live_runner_owner(tmp_path) is None
    assert lib.runner_owns_active_context_reason(tmp_path, epic_id="T-HUB-061") is None


def test_finish_plan_leaves_cursor_when_loop_owns_other_epic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _load_lib()
    monkeypatch.setenv("DEV_HUB", str(tmp_path))
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("EPIC_LOOP", raising=False)
    _write_live_owner(tmp_path, lib, epic_id="T-HUB-049", phase="QA")

    from harness.hooks.epic.core import save_epic_state
    from loop.mb_finish.impl import finish_plan
    from loop.mb_finish.schemas import MbFinishRequest

    plan = tmp_path / "memory-bank" / "back" / "plan" / "plan-T-HUB-061.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# Plan T-HUB-061\n", encoding="utf-8")
    original = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: QA\n"
        "epic_id: T-HUB-049\n"
        "step_id: T-HUB-049\n"
        "---\n\n"
        "## load_now\n"
        "1. [back/plan/T-HUB-049/yaml/decompose-index.yaml]"
        "(back/plan/T-HUB-049/yaml/decompose-index.yaml) — qa.\n\n"
        "## Handoff BACK QA — T-HUB-049\n"
        "- **Дальше:** выполнить `BACK QA`\n"
    )
    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(original, encoding="utf-8")
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-061",
            "armed_role": "BACK",
            "armed_plan": "memory-bank/back/plan/plan-T-HUB-061.md",
        },
    )

    res = finish_plan(
        MbFinishRequest(
            phase="BACK PLAN",
            step_id="PLAN",
            done_summary="plan ready",
            cwd=str(tmp_path),
        )
    )
    assert res.ok is True
    assert "cursor_unchanged_runner_owns_active_context" in res.diagnostic_codes
    assert (tmp_path / "memory-bank" / "activeContext.md").read_text(encoding="utf-8") == original


def test_prepare_halts_on_ac_armed_epic_split(tmp_path: Path) -> None:
    from loop.context_loop import prepare_session
    from harness.hooks.epic.core import save_epic_state

    (tmp_path / "memory-bank").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memory-bank" / "activeContext.md").write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: PLAN\n"
        "epic_id: T-HUB-061\n"
        "step_id: PLAN\n"
        "---\n\n"
        "## load_now\n"
        "1. [back/plan/T-HUB-061.md](back/plan/T-HUB-061.md) — plan.\n\n"
        "## Handoff BACK PLAN — T-HUB-061\n"
        "- **Дальше:** PLAN\n",
        encoding="utf-8",
    )
    save_epic_state(
        tmp_path,
        {
            "armed_epic": "T-HUB-049",
            "armed_role": "BACK",
            "armed_step": "QA",
            "phase": "QA",
            "active": True,
            "status": "armed",
        },
    )
    out = prepare_session(tmp_path)
    assert out["ok"] is False
    assert out.get("halt") is True
    assert out.get("diagnostic_code") == "active_context_identity_mismatch"


def test_filter_step_dirty_drops_foreign_memory_bank() -> None:
    from harness.hooks.session_resilience import filter_step_dirty

    kept = filter_step_dirty(
        [
            "memory-bank/back/plan/T-HUB-061/md/plan.md",
            "memory-bank/back/plan/T-HUB-049/yaml/decompose-index.yaml",
            "loop/context_loop.py",
        ],
        step_id="QA",
        epic_id="T-HUB-049",
    )
    assert kept == ["memory-bank/back/plan/T-HUB-049/yaml/decompose-index.yaml"]


def test_checkpoint_trace_skipped_for_qa_phase(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from harness.hooks.session_resilience import load_implement_checkpoint_trace

    assert load_implement_checkpoint_trace(tmp_path, "QA", "T-HUB-049") == []
    assert "expected one shard" not in capsys.readouterr().out


def _run_write_pretool(cwd: Path, file_path: str, contents: str = "") -> dict:
    proc = subprocess.run(
        [sys.executable, str(WRITE_PRETOOL)],
        input=json.dumps(
            {
                "tool_name": "Write",
                "cwd": str(cwd),
                "tool_input": {"file_path": file_path, "contents": contents},
            }
        ),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env={**os.environ, "DEV_HUB": str(cwd), "PROJECT_ROOT": str(cwd)},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def test_write_pretool_denies_foreign_active_context(tmp_path: Path) -> None:
    lib = _load_lib()
    _write_live_owner(tmp_path, lib, epic_id="T-HUB-049", phase="QA")
    denied = _run_write_pretool(
        tmp_path,
        str(tmp_path / "memory-bank" / "activeContext.md"),
        "---\nschema: loop-handoff/v1\nrole: BACK\nmode: PLAN\nepic_id: T-HUB-061\n---\n",
    )
    reason = denied.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert denied.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert "runner_owns_active_context" in reason
