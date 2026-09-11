"""End-to-end smoke tests for DSH runtime integration via context_loop and Python adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from loop import context_loop

ROOT = Path(__file__).resolve().parents[2]


def _seed_context(cwd: Path) -> None:
    plan_dir = cwd / "memory-bank" / "integration" / "plan" / "decompose-x"
    plan_dir.mkdir(parents=True)
    shard = plan_dir / "e16-foo.yaml"
    shard.write_text("schema: epic-decompose/v1\nstep_id: e16\n", encoding="utf-8")
    index = plan_dir / "index.yaml"
    index.write_text(
        "schema: epic-decompose/v1\n"
        "epic_id: decompose-x\n"
        "steps:\n"
        "  - id: e16\n"
        "    title: Step 16\n"
        "    status: pending\n",
        encoding="utf-8",
    )
    active = cwd / "memory-bank" / "activeContext.md"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: INTEG\n"
        "mode: IMPLEMENT\n"
        "epic_id: decompose-x\n"
        "step_id: e16\n"
        "---\n"
        "## load_now\n"
        "1. [e16-foo.yaml](integration/plan/decompose-x/e16-foo.yaml)\n"
        "2. [index.yaml](integration/plan/decompose-x/index.yaml)\n\n"
        "## Handoff INTEG IMPLEMENT\n"
        "- **Следующий:** `INTEG IMPLEMENT e16`\n"
        "- **Gaps:** none.\n",
        encoding="utf-8",
    )


def test_dsh_e2e_smoke_prepare_runtime_dsh(tmp_path: Path, monkeypatch) -> None:
    _seed_context(tmp_path)
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")
    monkeypatch.setenv("PROJECT_LOOP_IMPLEMENT_MODEL", "deepseek-coder")

    result = context_loop.prepare_session(tmp_path)

    assert result["runtime"] == "dsh"
    assert result["dsh_profile"].startswith("epic-")


def test_dsh_e2e_smoke_record_abort_completed(tmp_path: Path) -> None:
    _seed_context(tmp_path)
    state_file = tmp_path / ".claude" / "runtime" / "epic" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({
            "status": "running",
            "active": True,
            "armed_step": "e16",
            "armed_epic": "decompose-x",
            "session_id": "runner-sess-1",
            "last_finish_tool": {
                "name": "mb-finish implement",
                "session_id": "runner-sess-1",
                "epic_id": "decompose-x",
                "fingerprint": "sha256:finish",
                "step_id": "e16",
            },
            "last_finished_step": "e16",
        }),
        encoding="utf-8",
    )

    log = tmp_path / "dsh-session.jsonl"
    log.write_text(
        "SESSION_START session=runner-sess-1 mode=headless command=dsh\n"
        '{"type": "tool_started", "name": "exec_command"}\n'
        '{"type": "tool_completed", "name": "exec_command"}\n'
        '{"type": "session_end", "status": "completed"}\n'
        "SESSION_END session=runner-sess-1 exit_code=0\n",
        encoding="utf-8",
    )

    result = context_loop.record_abort(tmp_path, log_path=log, exit_code=0, runtime="dsh")

    assert result["ok"] is True
    assert result["outcome"] == "clean"
