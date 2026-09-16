"""Tests for LoopRunner outer orchestrator, lifecycle transitions, and action decisions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest
from harness.hooks._lib import RuntimeConfig
from loop.runner import (
    ContextPort,
    RunAction,
    RunOutcome,
    RunnerConfig,
    SessionPort,
    SessionRequest,
    SessionResult,
)
from loop.runner.orchestrator import (
    ContextLoopPort,
    IncidentTracker,
    LoopRunner,
)
from loop.runner.output import (
    format_abort_diagnostic,
    format_check_after_summary,
    format_cleared_incidents,
    format_dag_fanout,
    format_loop_complete,
    format_prepare_summary,
    format_pruned_logs,
    format_roadmap_advance,
    format_session_banner,
    format_session_exit,
    format_session_model_info,
    format_transient_cap_reached,
    format_transient_reprepare_complete,
    format_transient_reprepare_resync,
    format_transient_retry,
)


@pytest.fixture
def dummy_config(tmp_path: Path) -> RunnerConfig:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    state_dir = project_root / "runtime" / "dev-hub" / "epic"
    state_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = state_dir / "prompt.txt"
    prompt_file.write_text("test prompt")

    runtime = RuntimeConfig(
        session_timeout_sec=300,
        session_kill_grace_sec=10,
        transient_retry_max=3,
        subagent_retry_max=3,
        degraded_max=2,
        status_heartbeat_sec=60,
        stream_idle_timeout_sec=120,
        collaboration_wait_timeout_sec=120,
        permission_mode="bypass",
        sources={"session_timeout_sec": "default"},
        epic_runtime="codex",
    )

    return RunnerConfig(
        hub_root=tmp_path / "hub",
        project_root=project_root,
        state_dir=state_dir,
        runtime=runtime,
        permission_mode="bypass",
        headless=True,
        interactive=False,
        verbose=False,
        cli_model="gpt-5.6-terra",
    )


class MockContextPort:
    def __init__(self) -> None:
        self.prepare_responses: list[dict[str, Any]] = []
        self.check_after_responses: list[dict[str, Any]] = []
        self.record_abort_responses: list[dict[str, Any]] = []
        self.roadmap_responses: list[dict[str, Any]] = []
        self.dag_responses: list[dict[str, Any]] = []

        self.calls: list[tuple[str, Any]] = []

    def prepare_session(self, cwd: str | Path, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(("prepare_session", kwargs))
        if self.prepare_responses:
            return self.prepare_responses.pop(0)
        return {
            "ok": True,
            "model": "gpt-5.6-terra",
            "loop_phase": "IMPLEMENT",
            "armed_step": "s01",
            "fingerprint": "fp-123",
            "prompt_file": str(Path(cwd) / "runtime" / "dev-hub" / "epic" / "prompt.txt"),
            "runtime": "codex",
        }

    def check_after(self, cwd: str | Path, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(("check_after", kwargs))
        if self.check_after_responses:
            return self.check_after_responses.pop(0)
        return {"ok": True, "complete": False}

    def record_abort(self, cwd: str | Path, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(("record_abort", kwargs))
        if self.record_abort_responses:
            return self.record_abort_responses.pop(0)
        return {"ok": True, "exit_code": kwargs.get("exit_code", 0)}

    def roadmap_advance(self, cwd: str | Path, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(("roadmap_advance", kwargs))
        if self.roadmap_responses:
            return self.roadmap_responses.pop(0)
        return {"ok": True, "complete": True}

    def dag_fanout(self, cwd: str | Path, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(("dag_fanout", kwargs))
        if self.dag_responses:
            return self.dag_responses.pop(0)
        return {"ok": True, "complete": True}


class MockSessionInvoker:
    def __init__(self) -> None:
        self.results: list[SessionResult] = []
        self.invocations: list[SessionRequest] = []

    def invoke(self, request: SessionRequest) -> SessionResult:
        self.invocations.append(request)
        if self.results:
            return self.results.pop(0)
        return SessionResult(
            exit_code=0,
            runtime_id=request.runtime_id,
            log_file=request.log_file,
            interrupted=False,
        )


def test_clean_turn_lifecycle(dummy_config: RunnerConfig) -> None:
    """Verify LoopRunner completes prepare, invoke, record, and check-after in exact order."""
    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        ctx = MockContextPort()
        ctx.check_after_responses = [
            {"ok": True, "complete": False},
            {"ok": True, "stop": "EPIC_DONE", "complete": True},
        ]

        invoker = MockSessionInvoker()
        invoker.results = [
            SessionResult(exit_code=0, runtime_id="codex", log_file=dummy_config.state_dir / "session-1.log"),
            SessionResult(exit_code=0, runtime_id="codex", log_file=dummy_config.state_dir / "session-2.log"),
        ]

        mock_incident_tracker = MagicMock(spec=IncidentTracker)

        out_lines: list[str] = []
        err_lines: list[str] = []

        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=mock_incident_tracker,
            stdout=out_lines.append,
            stderr=err_lines.append,
            sleeper=lambda s: None,
        )

        outcome = runner.run()

        assert outcome.action == RunAction.COMPLETE
        assert outcome.exit_code == 0
        assert outcome.reason == "dag_journey"

        call_names = [name for name, _ in ctx.calls]
        assert call_names == [
            "prepare_session",
            "record_abort",
            "check_after",
            "prepare_session",
            "record_abort",
            "check_after",
            "dag_fanout",
        ]

        assert len(invoker.invocations) == 2
        assert invoker.invocations[0].session_id == "session-1"
        assert invoker.invocations[1].session_id == "session-2"

        assert mock_incident_tracker.record_trace.call_count == 2


def test_transient_retry(dummy_config: RunnerConfig) -> None:
    """Verify transient retry triggers context re-prepare and bounded exponential backoff."""
    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        ctx = MockContextPort()
        # Turn 1: session abort with retryable transient error, then re-prepare succeeds, then session 2 succeeds
        ctx.record_abort_responses = [
            {"ok": False, "retryable": True, "backoff_sec": 3, "reason": "rate_limit_exceeded"},
            {"ok": True, "exit_code": 0},
        ]
        ctx.check_after_responses = [
            {"ok": True, "stop": "EPIC_DONE", "complete": True},
        ]

        invoker = MockSessionInvoker()
        invoker.results = [
            SessionResult(exit_code=1, runtime_id="codex", log_file=dummy_config.state_dir / "session-1.log"),
            SessionResult(exit_code=0, runtime_id="codex", log_file=dummy_config.state_dir / "session-1-t2.log"),
        ]

        mock_tracker = MagicMock(spec=IncidentTracker)

        sleeps: list[float] = []
        out_lines: list[str] = []

        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=mock_tracker,
            stdout=out_lines.append,
            stderr=lambda s: None,
            sleeper=sleeps.append,
        )

        outcome = runner.run()

        assert outcome.action == RunAction.COMPLETE
        assert outcome.exit_code == 0
        assert sleeps == [3.0]
        assert len(invoker.invocations) == 2
        assert invoker.invocations[0].session_id == "session-1"
        assert invoker.invocations[1].session_id == "session-1-t2"


def test_transient_retry_subagent_timeout(dummy_config: RunnerConfig) -> None:
    """Verify native collaboration subagent timeout uses dedicated retry counter."""
    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        ctx = MockContextPort()
        ctx.record_abort_responses = [
            {"ok": False, "retryable": True, "backoff_sec": 1, "reason": "native collaboration wait timeout"},
            {"ok": True, "exit_code": 0},
        ]
        ctx.check_after_responses = [
            {"ok": True, "stop": "EPIC_DONE", "complete": True},
        ]

        invoker = MockSessionInvoker()
        invoker.results = [
            SessionResult(exit_code=1, runtime_id="codex", log_file=dummy_config.state_dir / "session-1.log"),
            SessionResult(exit_code=0, runtime_id="codex", log_file=dummy_config.state_dir / "session-1-t2.log"),
        ]

        mock_tracker = MagicMock(spec=IncidentTracker)

        out_lines: list[str] = []
        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=mock_tracker,
            stdout=out_lines.append,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )

        outcome = runner.run()

        assert outcome.action == RunAction.COMPLETE
        out_text = "".join(out_lines)
        assert "native collaboration retry: subagent retry 1/3" in out_text


def test_transient_retry_epic_completed(dummy_config: RunnerConfig) -> None:
    """Verify re-prepare detecting EPIC_DONE skips stale transient retry."""
    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        ctx = MockContextPort()
        ctx.record_abort_responses = [
            {"ok": False, "retryable": True, "backoff_sec": 0, "reason": "rate_limit"},
        ]
        # Re-prepare returns EPIC_DONE
        ctx.prepare_responses = [
            {"ok": True, "model": "gpt-5.6-terra", "loop_phase": "IMPLEMENT", "armed_step": "s01"},
            {"ok": True, "complete": True, "stop": "EPIC_DONE", "armed_step": "s01"},
            # Next outer prepare
            {"ok": True, "complete": True, "stop": "EPIC_DONE"},
        ]

        invoker = MockSessionInvoker()
        invoker.results = [
            SessionResult(exit_code=1, runtime_id="codex", log_file=dummy_config.state_dir / "session-1.log"),
        ]

        mock_tracker = MagicMock(spec=IncidentTracker)

        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=mock_tracker,
            stdout=lambda s: None,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )

        outcome = runner.run()

        assert outcome.action == RunAction.COMPLETE
        assert outcome.exit_code == 0


def test_action_decisions(dummy_config: RunnerConfig) -> None:
    """Verify action decisions (continue, complete, halt, NEED_HUMAN, DAG fanout)."""
    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        # 1. Halt with NEED_HUMAN
        ctx = MockContextPort()
        ctx.check_after_responses = [
            {"ok": False, "halt": True, "stop": "NEED_HUMAN: credentials missing"},
        ]

        invoker = MockSessionInvoker()
        mock_tracker = MagicMock(spec=IncidentTracker)
        mock_tracker.attempt_tier1.return_value = False

        err_lines: list[str] = []
        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=mock_tracker,
            stdout=lambda s: None,
            stderr=err_lines.append,
            sleeper=lambda s: None,
        )

        outcome = runner.run()
        assert outcome.action == RunAction.HALT
        assert outcome.exit_code == 1
        assert "need_human" in str(outcome.reason).lower()

        # 2. Tier-1 repair success recovers from halt
        ctx2 = MockContextPort()
        ctx2.check_after_responses = [
            {"ok": False, "halt": True, "stop": "gate_integrity_mismatch"},
            {"ok": True, "complete": True, "stop": "EPIC_DONE"},
        ]
        mock_tracker2 = MagicMock(spec=IncidentTracker)
        mock_tracker2.attempt_tier1.side_effect = [True, False]

        runner2 = LoopRunner(
            dummy_config,
            context_port=ctx2,
            session_invoker=invoker,
            incident_tracker=mock_tracker2,
            stdout=lambda s: None,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )

        outcome2 = runner2.run()
        assert outcome2.action == RunAction.COMPLETE
        assert outcome2.exit_code == 0

        # 3. User interrupt produces 130
        invoker3 = MockSessionInvoker()
        invoker3.results = [
            SessionResult(exit_code=130, runtime_id="codex", log_file=dummy_config.state_dir / "session-1.log", interrupted=True),
        ]
        runner3 = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker3,
            incident_tracker=mock_tracker,
            stdout=lambda s: None,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )
        outcome3 = runner3.run()
        assert outcome3.action == RunAction.HALT
        assert outcome3.exit_code == 130

        # 3b. unsupported-tool exit 126 with interrupted=True must retry, not fake Ctrl+C
        ctx126 = MockContextPort()
        ctx126.record_abort_responses = [
            {
                "ok": False,
                "retryable": True,
                "backoff_sec": 0,
                "reason": "unsupported_tool_call: malformed_tool_call",
            },
            {"ok": True, "exit_code": 0},
        ]
        ctx126.check_after_responses = [
            {"ok": True, "stop": "EPIC_DONE", "complete": True},
        ]
        invoker126 = MockSessionInvoker()
        invoker126.results = [
            SessionResult(
                exit_code=126,
                runtime_id="codex",
                log_file=dummy_config.state_dir / "session-1.log",
                interrupted=True,
            ),
            SessionResult(
                exit_code=0,
                runtime_id="codex",
                log_file=dummy_config.state_dir / "session-1-t2.log",
                interrupted=False,
            ),
        ]
        err126: list[str] = []
        runner126 = LoopRunner(
            dummy_config,
            context_port=ctx126,
            session_invoker=invoker126,
            incident_tracker=mock_tracker,
            stdout=lambda s: None,
            stderr=err126.append,
            sleeper=lambda s: None,
        )
        outcome126 = runner126.run()
        assert outcome126.action == RunAction.COMPLETE
        assert outcome126.reason != "user_interrupt"
        assert not any("user interrupt" in line for line in err126)
        assert len(invoker126.invocations) == 2
        assert any(c[0] == "record_abort" for c in ctx126.calls)

        # 4. Model required missing produces 2
        ctx4 = MockContextPort()
        ctx4.prepare_responses = [
            {"ok": True, "model": None, "loop_phase": "IMPLEMENT", "armed_step": "s01"},
        ]
        runner4 = LoopRunner(
            RunnerConfig(
                hub_root=dummy_config.hub_root,
                project_root=dummy_config.project_root,
                state_dir=dummy_config.state_dir,
                runtime=dummy_config.runtime,
                permission_mode="bypass",
                headless=True,
                interactive=False,
                verbose=False,
                cli_model=None,
            ),
            context_port=ctx4,
            session_invoker=invoker,
            incident_tracker=mock_tracker,
            stdout=lambda s: None,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )
        outcome4 = runner4.run()
        assert outcome4.action == RunAction.HALT
        assert outcome4.exit_code == 2
        assert outcome4.reason == "model_required"


def test_log_pruning(tmp_path: Path, dummy_config: RunnerConfig) -> None:
    """Verify old session logs beyond keep count are pruned."""
    logs_dir = dummy_config.state_dir
    logs: list[Path] = []
    for i in range(15):
        p = logs_dir / f"session-{i}.log"
        p.write_text(f"session {i}")
        logs.append(p)
        # Stagger modification times
        os.utime(p, (1000 + i, 1000 + i))

    runner = LoopRunner(dummy_config)
    removed, kept = runner.prune_logs(logs_dir, keep=5)

    assert removed == 10
    assert kept == 5
    remaining = list(logs_dir.glob("session-*.log"))
    assert len(remaining) == 5


def test_pure_output_formatters() -> None:
    """Verify formatting functions in output.py."""
    assert "SESSION 1" in format_session_banner(1)
    assert format_pruned_logs(3, 10) == "==> pruned 3 old session log(s); kept 10"
    assert format_session_exit("codex", 0, 1, 3) == "==> codex exit=0 (try 1/3)"
    assert format_session_model_info("m1", "IMP", "s01", "cli") == "==> session model=m1 phase=IMP step=s01 source=cli"
    assert format_loop_complete("stop marker") == "==> LOOP COMPLETE (stop marker)"

    prep_out = format_prepare_summary({"ok": True, "phase": "IMP", "armed_step": "s02"})
    assert "==> prepare: ok" in prep_out
    assert "==> working: IMP step=s02" in prep_out

    transient_lines = format_transient_retry("api_error", 5, is_subagent=True, subagent_attempt=1, max_subagent=3)
    assert any("TRANSIENT API abort" in l for l in transient_lines)
    assert any("native collaboration retry" in l for l in transient_lines)


def test_orchestrator_preserves_open_incidents_on_start(
    dummy_config: RunnerConfig,
) -> None:
    """Verify that open incidents in incidents.jsonl are preserved across orchestrator startup and runs."""
    from loop.incidents.schema import IncidentRecord, SCHEMA_LOOP_INCIDENT
    from loop.incidents.store import append_incident, parse_incidents_jsonl

    # Setup an open incident in state_dir / incidents.jsonl
    # dummy_config.state_dir is the epic directory for dummy_config
    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-restart-persistence-001",
        status="open",
        opened_at="2026-09-15T12:00:00Z",
        project_root=str(dummy_config.project_root),
        epic_id="T-HUB-101",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="session-prev",
        source="check_after",
        diagnostic_codes=["gate_integrity_mismatch"],
        fingerprint="fp-persist-1",
        metadata={"persisted": True},
    )
    append_incident(dummy_config.state_dir, inc)

    # Confirm incident is open before running orchestrator
    records_before = parse_incidents_jsonl(dummy_config.state_dir / "incidents.jsonl")
    assert len(records_before) == 1
    assert records_before[0].status == "open"
    assert records_before[0].incident_id == "inc-restart-persistence-001"

    with patch.dict(os.environ, {"EPIC_CHAIN_ROADMAP": "0"}, clear=False):
        ctx = MockContextPort()
        ctx.check_after_responses = [
            {"ok": True, "stop": "EPIC_DONE", "complete": True},
        ]
        invoker = MockSessionInvoker()
        invoker.results = [
            SessionResult(
                exit_code=0,
                runtime_id="codex",
                log_file=dummy_config.state_dir / "session-1.log",
            )
        ]

        # Use real IncidentTracker with tier1_enabled=False to avoid triggering autofix
        real_tracker = IncidentTracker(tier1_enabled=False)

        runner = LoopRunner(
            dummy_config,
            context_port=ctx,
            session_invoker=invoker,
            incident_tracker=real_tracker,
            stdout=lambda s: None,
            stderr=lambda s: None,
            sleeper=lambda s: None,
        )

        outcome = runner.run()
        assert outcome.action == RunAction.COMPLETE
        assert outcome.exit_code == 0

    # Confirm incident remains open after orchestrator run (forensic persistence)
    records_after = parse_incidents_jsonl(dummy_config.state_dir / "incidents.jsonl")
    assert len(records_after) == 1
    assert records_after[0].status == "open"
    assert records_after[0].incident_id == "inc-restart-persistence-001"
    assert records_after[0].metadata.get("persisted") is True


def test_incident_tracker_record_trace_writes_trace(tmp_path: Path) -> None:
    """Verify IncidentTracker.record_trace resolves canonical epic_dir and writes session-trace.jsonl."""
    from loop.incidents.trace import read_session_trace_tail
    try:
        from epic_paths import epic_dir
    except ImportError:
        from harness.hooks.epic_paths import epic_dir

    tracker = IncidentTracker()
    tracker.record_trace(
        tmp_path,
        phase="BACK IMPLEMENT",
        action="decide_after_action",
        decide="continue",
        episode_id="ep-42",
        detail={"score": 100},
    )

    edir = epic_dir(tmp_path)
    assert (edir / "session-trace.jsonl").is_file()
    traces = read_session_trace_tail(edir)
    assert len(traces) == 1
    assert traces[0]["phase"] == "BACK IMPLEMENT"
    assert traces[0]["action"] == "decide_after_action"
    assert traces[0]["decide"] == "continue"
    assert traces[0]["episode_id"] == "ep-42"
    assert traces[0]["detail"] == {"score": 100}


def test_incident_tracker_attempt_tier1_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify attempt_tier1 immediately returns False when disabled or disabled via env."""
    tracker_disabled = IncidentTracker(tier1_enabled=False)
    assert tracker_disabled.attempt_tier1(tmp_path) is False

    tracker_enabled = IncidentTracker(tier1_enabled=True)
    monkeypatch.setenv("EPIC_INCIDENT_TIER1", "0")
    assert tracker_enabled.attempt_tier1(tmp_path) is False


def test_incident_tracker_attempt_tier1_no_open_incidents(tmp_path: Path) -> None:
    """Verify attempt_tier1 returns False when no open incidents exist."""
    tracker = IncidentTracker(tier1_enabled=True)
    assert tracker.attempt_tier1(tmp_path) is False


def test_incident_tracker_attempt_tier1_success(tmp_path: Path) -> None:
    """Verify attempt_tier1 runs tier1 session and resolves incident on success."""
    from loop.incidents.schema import IncidentRecord, SCHEMA_LOOP_INCIDENT
    from loop.incidents.store import append_incident, list_open_incidents
    from loop.incidents.tier1_runner import Tier1Result
    try:
        from epic_paths import epic_dir
    except ImportError:
        from harness.hooks.epic_paths import epic_dir

    edir = epic_dir(tmp_path)
    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-tier1-test-01",
        status="open",
        opened_at="2026-09-15T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="T-HUB-101",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="session-1",
        source="check_after",
        diagnostic_codes=["syntax_error"],
        fingerprint="fp-1",
    )
    append_incident(edir, inc)
    assert len(list_open_incidents(edir)) == 1

    tracker = IncidentTracker(tier1_enabled=True)
    with patch("loop.incidents.tier1_runner.should_attempt_tier1", return_value=True), patch(
        "loop.incidents.tier1_runner.run_tier1_session", return_value=Tier1Result(success=True)
    ):
        result = tracker.attempt_tier1(tmp_path)
        assert result is True

    # Incident should now be resolved
    assert len(list_open_incidents(edir)) == 0


def test_incident_tracker_attempt_tier1_failure(tmp_path: Path) -> None:
    """Verify attempt_tier1 returns False and leaves incident open when tier1 session fails."""
    from loop.incidents.schema import IncidentRecord, SCHEMA_LOOP_INCIDENT
    from loop.incidents.store import append_incident, list_open_incidents
    from loop.incidents.tier1_runner import Tier1Result
    try:
        from epic_paths import epic_dir
    except ImportError:
        from harness.hooks.epic_paths import epic_dir

    edir = epic_dir(tmp_path)
    inc = IncidentRecord(
        schema=SCHEMA_LOOP_INCIDENT,
        incident_id="inc-tier1-test-02",
        status="open",
        opened_at="2026-09-15T12:00:00Z",
        project_root=str(tmp_path),
        epic_id="T-HUB-101",
        step_id="s01",
        phase="BACK IMPLEMENT",
        session_id="session-1",
        source="check_after",
        diagnostic_codes=["syntax_error"],
        fingerprint="fp-2",
    )
    append_incident(edir, inc)
    assert len(list_open_incidents(edir)) == 1

    tracker = IncidentTracker(tier1_enabled=True)
    with patch("loop.incidents.tier1_runner.should_attempt_tier1", return_value=True), patch(
        "loop.incidents.tier1_runner.run_tier1_session", return_value=Tier1Result(success=False)
    ):
        result = tracker.attempt_tier1(tmp_path)
        assert result is False

    # Incident should remain open
    assert len(list_open_incidents(edir)) == 1
