"""Characterization tests for supervisor halt parity, decision routing, and error behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from harness.hooks._lib import RuntimeConfig
from loop.halt_logic import decide_after_action
from loop.runner import RunAction, RunOutcome, RunnerConfig
from loop.runner.orchestrator import LoopRunner


ROOT = Path(__file__).resolve().parents[2]


def test_decide_after_action_wires_halt_and_continue() -> None:
    # NEED_HUMAN halts
    assert decide_after_action({"stop": "NEED_HUMAN — blocked on input"}) == "halt"

    # EPIC_DONE completes
    assert decide_after_action({"stop": "EPIC_DONE"}) == "complete"

    # normal continue
    assert decide_after_action({"ok": True, "complete": False, "halt": False}) == "continue"

    # repair exhausted halts
    assert decide_after_action({"repair_exhausted": True}) == "halt"

    # fallback halts
    assert decide_after_action({"ok": False}) == "halt"


def test_prepare_fail_closed_halts(tmp_path: Path) -> None:
    state_dir = tmp_path / "runtime" / "dev-hub" / "epic"
    state_dir.mkdir(parents=True)
    cfg = RunnerConfig(
        hub_root=tmp_path,
        project_root=tmp_path,
        state_dir=state_dir,
        runtime=RuntimeConfig(
            session_timeout_sec=300,
            session_kill_grace_sec=10,
            transient_retry_max=3,
            subagent_retry_max=3,
            degraded_max=2,
            status_heartbeat_sec=60,
            stream_idle_timeout_sec=120,
            collaboration_wait_timeout_sec=120,
            permission_mode="bypass",
            sources={},
            epic_runtime="claude",
        ),
        permission_mode="bypass",
        headless=True,
        interactive=False,
        verbose=False,
    )
    mock_context = MagicMock()
    mock_context.prepare_session.return_value = {
        "ok": False,
        "halt": True,
        "reason": "prepare fail-closed test",
    }
    mock_session = MagicMock()

    runner = LoopRunner(config=cfg, context_port=mock_context, session_invoker=mock_session)
    outcome = runner.run()

    assert outcome.action == RunAction.HALT
    assert outcome.exit_code == 1
    assert mock_session.invoke.call_count == 0


def test_runtime_adapter_preparation_failure_halts_without_session(tmp_path: Path) -> None:
    state_dir = tmp_path / "runtime" / "dev-hub" / "epic"
    state_dir.mkdir(parents=True)
    cfg = RunnerConfig(
        hub_root=tmp_path,
        project_root=tmp_path,
        state_dir=state_dir,
        runtime=RuntimeConfig(
            session_timeout_sec=300,
            session_kill_grace_sec=10,
            transient_retry_max=3,
            subagent_retry_max=3,
            degraded_max=2,
            status_heartbeat_sec=60,
            stream_idle_timeout_sec=120,
            collaboration_wait_timeout_sec=120,
            permission_mode="bypass",
            sources={},
            epic_runtime="claude",
        ),
        permission_mode="bypass",
        headless=True,
        interactive=False,
        verbose=False,
    )
    mock_context = MagicMock()
    mock_context.prepare_session.return_value = {
        "ok": True,
        "loop_phase": "IMPLEMENT",
        "model": "test-model",
        "fingerprint": "fp-1",
        "prompt_file": str(state_dir / "prompt.txt"),
    }
    mock_session = MagicMock()
    mock_session.invoke.return_value = MagicMock(
        preparation_failed=True,
        exit_code=1,
        outcome="adapter_preparation_failed",
    )

    runner = LoopRunner(config=cfg, context_port=mock_context, session_invoker=mock_session)
    outcome = runner.run()

    assert outcome.action == RunAction.HALT
    assert outcome.exit_code == 130
