"""Characterization and contract tests for loop.runner typed boundaries."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from harness.hooks._lib import RuntimeConfig
from loop.runner import (
    ContextPort,
    PreflightCheckResult,
    RunAction,
    RunOutcome,
    RunnerConfig,
    SessionPort,
    SessionRequest,
    SessionResult,
)


def _sample_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        session_timeout_sec=300,
        session_kill_grace_sec=10,
        transient_retry_max=3,
        subagent_retry_max=2,
        degraded_max=2,
        status_heartbeat_sec=30,
        stream_idle_timeout_sec=60,
        collaboration_wait_timeout_sec=120,
        permission_mode="bypass",
        sources={"PROJECT_LOOP_TIMEOUT": "default"},
        epic_runtime="claude",
    )


class TestRunAction:
    def test_enum_members_and_string_values(self) -> None:
        assert RunAction.CONTINUE == "continue"
        assert RunAction.COMPLETE == "complete"
        assert RunAction.HALT == "halt"
        assert str(RunAction.CONTINUE) == "continue"
        assert isinstance(RunAction.CONTINUE, str)

    def test_enum_lookup(self) -> None:
        assert RunAction("continue") is RunAction.CONTINUE
        assert RunAction("complete") is RunAction.COMPLETE
        assert RunAction("halt") is RunAction.HALT

        with pytest.raises(ValueError):
            RunAction("invalid_action")


class TestRunOutcome:
    def test_creation_and_fields(self) -> None:
        outcome = RunOutcome(action=RunAction.CONTINUE, exit_code=0, reason="step finished")
        assert outcome.action == RunAction.CONTINUE
        assert outcome.exit_code == 0
        assert outcome.reason == "step finished"

    def test_immutability(self) -> None:
        outcome = RunOutcome(action=RunAction.COMPLETE, exit_code=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.exit_code = 1  # type: ignore[misc]

    def test_serialization(self) -> None:
        outcome = RunOutcome(action=RunAction.HALT, exit_code=1, reason="timeout")
        d = outcome.to_dict()
        assert d == {"action": "halt", "exit_code": 1, "reason": "timeout"}
        assert json.loads(json.dumps(d)) == d


class TestPreflightCheckResult:
    def test_success_creation(self) -> None:
        res = PreflightCheckResult(ok=True)
        assert res.ok is True
        assert res.reason is None
        assert res.exit_code == 0
        assert res.diagnostic_code is None
        assert res.details == {}
        assert bool(res.ok) is True

    def test_failure_creation(self) -> None:
        res = PreflightCheckResult(
            ok=False,
            reason="missing binary",
            exit_code=127,
            diagnostic_code="MISSING_BIN",
            details={"binary": "claude"},
        )
        assert res.ok is False
        assert res.reason == "missing binary"
        assert res.exit_code == 127
        assert res.diagnostic_code == "MISSING_BIN"
        assert res.details["binary"] == "claude"

    def test_immutability(self) -> None:
        res = PreflightCheckResult(ok=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            res.ok = False  # type: ignore[misc]

    def test_serialization(self) -> None:
        res = PreflightCheckResult(
            ok=False,
            reason="lock busy",
            exit_code=1,
            diagnostic_code="LOCK_CONTENDED",
            details={"lock_path": "/tmp/lock"},
        )
        d = res.to_dict()
        assert d == {
            "ok": False,
            "reason": "lock busy",
            "exit_code": 1,
            "diagnostic_code": "LOCK_CONTENDED",
            "details": {"lock_path": "/tmp/lock"},
        }
        assert json.loads(json.dumps(d)) == d


class TestRunnerConfig:
    def test_creation_and_types(self, tmp_path: Path) -> None:
        rc = _sample_runtime_config()
        config = RunnerConfig(
            hub_root=tmp_path / "hub",
            project_root=tmp_path / "project",
            state_dir=tmp_path / "state",
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=True,
            cli_model="claude-3-5-sonnet",
            epic_spec="s01",
            epic_id="T-HUB-086",
            mode="implement",
            extra_args=("--debug", "--json"),
        )
        assert config.hub_root == tmp_path / "hub"
        assert config.project_root == tmp_path / "project"
        assert config.state_dir == tmp_path / "state"
        assert config.runtime == rc
        assert config.permission_mode == "bypass"
        assert config.headless is True
        assert config.interactive is False
        assert config.verbose is True
        assert config.cli_model == "claude-3-5-sonnet"
        assert config.epic_spec == "s01"
        assert config.epic_id == "T-HUB-086"
        assert config.mode == "implement"
        assert config.extra_args == ("--debug", "--json")

    def test_string_path_normalization(self, tmp_path: Path) -> None:
        rc = _sample_runtime_config()
        config = RunnerConfig(
            hub_root=str(tmp_path / "hub"),  # type: ignore[arg-type]
            project_root=str(tmp_path / "project"),  # type: ignore[arg-type]
            state_dir=str(tmp_path / "state"),  # type: ignore[arg-type]
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=False,
            extra_args=["--opt1", "--opt2"],  # type: ignore[arg-type]
        )
        assert isinstance(config.hub_root, Path)
        assert isinstance(config.project_root, Path)
        assert isinstance(config.state_dir, Path)
        assert isinstance(config.extra_args, tuple)

    def test_immutability(self, tmp_path: Path) -> None:
        rc = _sample_runtime_config()
        config = RunnerConfig(
            hub_root=tmp_path / "hub",
            project_root=tmp_path / "project",
            state_dir=tmp_path / "state",
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=False,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.headless = False  # type: ignore[misc]

    def test_serialization(self, tmp_path: Path) -> None:
        rc = _sample_runtime_config()
        config = RunnerConfig(
            hub_root=tmp_path / "hub",
            project_root=tmp_path / "project",
            state_dir=tmp_path / "state",
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=False,
            extra_args=("--foo", "bar"),
        )
        d = config.to_dict()
        assert d["hub_root"] == str(tmp_path / "hub")
        assert d["runtime"]["session_timeout_sec"] == 300
        assert d["extra_args"] == ["--foo", "bar"]
        assert json.loads(json.dumps(d)) == d


class TestSessionRequest:
    def test_creation_and_types(self, tmp_path: Path) -> None:
        req = SessionRequest(
            session_id="sess-123",
            prompt_file=tmp_path / "prompt.txt",
            runtime_id="claude",
            phase="implement",
            model="gpt-5",
            mode="headless",
            log_file=tmp_path / "session.log",
            timeout_sec=300,
            kill_grace_sec=10,
            heartbeat_sec=30,
            idle_timeout_sec=60,
            permission_mode="bypass",
            extra_args=("--trace",),
            project_root=tmp_path / "proj",
            hub_root=tmp_path / "hub",
            runtime_extras={"custom": "value"},
        )
        assert req.session_id == "sess-123"
        assert req.prompt_file == tmp_path / "prompt.txt"
        assert req.runtime_id == "claude"
        assert req.phase == "implement"
        assert req.model == "gpt-5"
        assert req.mode == "headless"
        assert req.log_file == tmp_path / "session.log"
        assert req.timeout_sec == 300
        assert req.kill_grace_sec == 10
        assert req.heartbeat_sec == 30
        assert req.idle_timeout_sec == 60
        assert req.permission_mode == "bypass"
        assert req.extra_args == ("--trace",)
        assert req.project_root == tmp_path / "proj"
        assert req.hub_root == tmp_path / "hub"
        assert req.runtime_extras == {"custom": "value"}

    def test_string_path_and_list_normalization(self, tmp_path: Path) -> None:
        req = SessionRequest(
            session_id="sess-123",
            prompt_file=str(tmp_path / "prompt.txt"),  # type: ignore[arg-type]
            runtime_id="claude",
            phase="implement",
            model=None,
            mode="headless",
            log_file=str(tmp_path / "session.log"),  # type: ignore[arg-type]
            timeout_sec=300,
            kill_grace_sec=10,
            heartbeat_sec=None,
            idle_timeout_sec=None,
            permission_mode="bypass",
            extra_args=["--foo"],  # type: ignore[arg-type]
            project_root=str(tmp_path / "proj"),  # type: ignore[arg-type]
            hub_root=str(tmp_path / "hub"),  # type: ignore[arg-type]
        )
        assert isinstance(req.prompt_file, Path)
        assert isinstance(req.log_file, Path)
        assert isinstance(req.project_root, Path)
        assert isinstance(req.hub_root, Path)
        assert isinstance(req.extra_args, tuple)

    def test_immutability(self, tmp_path: Path) -> None:
        req = SessionRequest(
            session_id="sess-123",
            prompt_file=tmp_path / "prompt.txt",
            runtime_id="claude",
            phase="implement",
            model=None,
            mode="headless",
            log_file=tmp_path / "session.log",
            timeout_sec=300,
            kill_grace_sec=10,
            heartbeat_sec=None,
            idle_timeout_sec=None,
            permission_mode="bypass",
            extra_args=(),
            project_root=tmp_path / "proj",
            hub_root=tmp_path / "hub",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.session_id = "sess-456"  # type: ignore[misc]

    def test_serialization(self, tmp_path: Path) -> None:
        req = SessionRequest(
            session_id="sess-123",
            prompt_file=tmp_path / "prompt.txt",
            runtime_id="claude",
            phase="implement",
            model="sonnet",
            mode="headless",
            log_file=tmp_path / "session.log",
            timeout_sec=300,
            kill_grace_sec=10,
            heartbeat_sec=15,
            idle_timeout_sec=45,
            permission_mode="bypass",
            extra_args=("-v",),
            project_root=tmp_path / "proj",
            hub_root=tmp_path / "hub",
            runtime_extras={"k": "v"},
        )
        d = req.to_dict()
        assert d["session_id"] == "sess-123"
        assert d["prompt_file"] == str(tmp_path / "prompt.txt")
        assert d["extra_args"] == ["-v"]
        assert d["runtime_extras"] == {"k": "v"}
        assert json.loads(json.dumps(d)) == d


class TestSessionResult:
    def test_creation_and_fields(self, tmp_path: Path) -> None:
        res = SessionResult(exit_code=0, runtime_id="claude", log_file=tmp_path / "sess.log")
        assert res.exit_code == 0
        assert res.runtime_id == "claude"
        assert res.log_file == tmp_path / "sess.log"
        assert res.interrupted is False

    def test_interrupted_flag(self, tmp_path: Path) -> None:
        res = SessionResult(
            exit_code=130,
            runtime_id="claude",
            log_file=str(tmp_path / "sess.log"),  # type: ignore[arg-type]
            interrupted=True,
        )
        assert res.exit_code == 130
        assert res.interrupted is True
        assert isinstance(res.log_file, Path)

    def test_immutability(self, tmp_path: Path) -> None:
        res = SessionResult(exit_code=0, runtime_id="claude", log_file=tmp_path / "sess.log")
        with pytest.raises(dataclasses.FrozenInstanceError):
            res.exit_code = 1  # type: ignore[misc]

    def test_serialization(self, tmp_path: Path) -> None:
        res = SessionResult(
            exit_code=130,
            runtime_id="codex",
            log_file=tmp_path / "sess.log",
            interrupted=True,
        )
        d = res.to_dict()
        assert d == {
            "exit_code": 130,
            "runtime_id": "codex",
            "log_file": str(tmp_path / "sess.log"),
            "interrupted": True,
        }
        assert json.loads(json.dumps(d)) == d


class TestPortsAndProtocols:
    def test_context_port_protocol_implementation(self, tmp_path: Path) -> None:
        class FakeContextPort:
            def prepare_session(
                self,
                cwd: str | Path,
                *,
                model: str | None = None,
                runtime: str | None = None,
                _chain_depth: int = 0,
            ) -> Mapping[str, Any]:
                return {"ok": True, "action": "run"}

            def check_after(
                self,
                cwd: str | Path,
                *,
                fingerprint_before: str | None = None,
            ) -> Mapping[str, Any]:
                return {"ok": True, "action": "continue"}

            def record_abort(
                self,
                cwd: str | Path,
                *,
                log_path: str | Path,
                exit_code: int,
                attempt: int = 1,
                runtime: str = "claude",
            ) -> Mapping[str, Any]:
                return {"ok": True, "retryable": False}

        fake = FakeContextPort()
        assert isinstance(fake, ContextPort)

        # Call the methods to ensure contract compatibility
        res_prep = fake.prepare_session(tmp_path)
        assert res_prep["ok"] is True
        res_check = fake.check_after(tmp_path)
        assert res_check["action"] == "continue"
        res_abort = fake.record_abort(tmp_path, log_path=tmp_path / "log", exit_code=1)
        assert res_abort["retryable"] is False

    def test_session_port_protocol_implementation(self, tmp_path: Path) -> None:
        class FakeSessionPort:
            def invoke(self, request: SessionRequest) -> SessionResult:
                return SessionResult(
                    exit_code=0,
                    runtime_id=request.runtime_id,
                    log_file=request.log_file,
                    interrupted=False,
                )

        fake = FakeSessionPort()
        assert isinstance(fake, SessionPort)

        req = SessionRequest(
            session_id="test",
            prompt_file=tmp_path / "prompt",
            runtime_id="claude",
            phase="implement",
            model=None,
            mode="headless",
            log_file=tmp_path / "log",
            timeout_sec=10,
            kill_grace_sec=2,
            heartbeat_sec=None,
            idle_timeout_sec=None,
            permission_mode="bypass",
            extra_args=(),
            project_root=tmp_path,
            hub_root=tmp_path,
        )
        result = fake.invoke(req)
        assert result.exit_code == 0
        assert result.runtime_id == "claude"
        assert result.log_file == tmp_path / "log"


class TestContextLoopCompatibility:
    def test_context_loop_adapter_satisfies_port(self) -> None:
        import loop.context_loop as cl

        class RealContextLoopAdapter:
            def prepare_session(
                self,
                cwd: str | Path,
                *,
                model: str | None = None,
                runtime: str | None = None,
                _chain_depth: int = 0,
            ) -> Mapping[str, Any]:
                return cl.prepare_session(cwd, model=model, runtime=runtime, _chain_depth=_chain_depth)

            def check_after(
                self,
                cwd: str | Path,
                *,
                fingerprint_before: str | None = None,
            ) -> Mapping[str, Any]:
                return cl.check_after(cwd, fingerprint_before=fingerprint_before)

            def record_abort(
                self,
                cwd: str | Path,
                *,
                log_path: str | Path,
                exit_code: int,
                attempt: int = 1,
                runtime: str = "claude",
            ) -> Mapping[str, Any]:
                return cl.record_abort(cwd, log_path=log_path, exit_code=exit_code, attempt=attempt, runtime=runtime)

        adapter = RealContextLoopAdapter()
        assert isinstance(adapter, ContextPort)


class TestReconstructionAndAsdict:
    def test_runner_config_asdict_and_reconstruct(self, tmp_path: Path) -> None:
        rc = _sample_runtime_config()
        config = RunnerConfig(
            hub_root=tmp_path / "hub",
            project_root=tmp_path / "project",
            state_dir=tmp_path / "state",
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=False,
            cli_model="gpt-5",
            epic_spec="s01",
            epic_id="T-HUB-086",
            mode="implement",
            extra_args=("--trace",),
        )
        as_dict_res = dataclasses.asdict(config)
        assert as_dict_res["permission_mode"] == "bypass"
        assert as_dict_res["runtime"]["session_timeout_sec"] == 300

    def test_session_request_asdict_and_reconstruct(self, tmp_path: Path) -> None:
        req = SessionRequest(
            session_id="sess-999",
            prompt_file=tmp_path / "prompt.txt",
            runtime_id="codex",
            phase="implement",
            model="gpt-5",
            mode="headless",
            log_file=tmp_path / "sess.log",
            timeout_sec=300,
            kill_grace_sec=10,
            heartbeat_sec=None,
            idle_timeout_sec=None,
            permission_mode="bypass",
            extra_args=(),
            project_root=tmp_path / "proj",
            hub_root=tmp_path / "hub",
            runtime_extras={"stream_filter": "codex"},
        )
        as_dict_res = dataclasses.asdict(req)
        assert as_dict_res["runtime_id"] == "codex"
        assert as_dict_res["runtime_extras"]["stream_filter"] == "codex"
