"""Tests for provider-neutral SessionInvoker, runtime adapters, and resilience wiring."""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from harness.hooks.session_resilience import SessionExecutionResult
from loop.runner import SessionRequest, SessionResult
from loop.runner.session import SessionInvoker
from loop.runtime_adapters.base import (
    RuntimeAdapter,
    RuntimePreparationResult,
    SessionAnalysis,
    SessionContext,
)
from loop.runtime_adapters.claude import ClaudeAdapter
from loop.runtime_adapters.codex import CodexAdapter
from loop.runtime_adapters.dsh import DshAdapter


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Path]:
    hub_root = tmp_path / "hub"
    project_root = tmp_path / "project"
    state_dir = project_root / ".state"
    hub_root.mkdir(parents=True)
    project_root.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    prompt_file = state_dir / "prompt.txt"
    prompt_file.write_text("Test prompt for session", encoding="utf-8")
    log_file = state_dir / "session-1.log"

    # Create dummy stream filters
    hooks_dir = hub_root / "harness" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "epic_stream_filter.py").write_text("import sys\nfor line in sys.stdin: sys.stdout.write(line)\n")
    (hooks_dir / "epic_codex_stream_filter.py").write_text("import sys\nfor line in sys.stdin: sys.stdout.write(line)\n")
    (hooks_dir / "dsh_stream_filter.py").write_text("import sys\nfor line in sys.stdin: sys.stdout.write(line)\n")

    return {
        "hub_root": hub_root,
        "project_root": project_root,
        "state_dir": state_dir,
        "prompt_file": prompt_file,
        "log_file": log_file,
    }


def _make_request(
    workspace: dict[str, Path],
    runtime_id: str,
    mode: str = "headless",
    model: str | None = None,
    extras: dict[str, Any] | None = None,
) -> SessionRequest:
    return SessionRequest(
        session_id="test-1",
        prompt_file=workspace["prompt_file"],
        runtime_id=runtime_id,
        phase="IMPLEMENT",
        model=model,
        mode=mode,
        log_file=workspace["log_file"],
        timeout_sec=30,
        kill_grace_sec=5,
        heartbeat_sec=10,
        idle_timeout_sec=20,
        permission_mode="dangerously-skip-permissions",
        extra_args=("--verbose",),
        project_root=workspace["project_root"],
        hub_root=workspace["hub_root"],
        runtime_extras=extras or {},
    )


# ============================================================================
# CP1: test_invoke_providers
# ============================================================================

def test_invoke_providers_claude_delegation(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="claude", model="claude-3-5-sonnet")

    with patch("loop.runner.session.execute_session") as mock_exec,          patch.object(ClaudeAdapter, "resolve_binary", return_value="claude"):
        mock_exec.return_value = SessionExecutionResult(
            exit_code=0,
            log_file=req.log_file,
            interrupted=False,
        )

        res = invoker.invoke(req)

        assert res.exit_code == 0
        assert res.runtime_id == "claude"
        assert res.log_file == req.log_file

        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == workspace["hub_root"]
        assert kwargs["progress_mode"] == "tool_json"
        assert kwargs["stdin_text"] is None
        assert "claude" in kwargs["command"][0]
        assert "--add-dir" in kwargs["command"]
        assert str(workspace["project_root"]) in kwargs["command"]
        assert "--dangerously-skip-permissions" in kwargs["command"]
        assert "--model" in kwargs["command"]
        assert "claude-3-5-sonnet" in kwargs["command"]
        assert kwargs["stream_filter_cmd"] == [
            sys.executable,
            str(workspace["hub_root"] / "harness" / "hooks" / "epic_stream_filter.py"),
        ]


def test_invoke_providers_dsh_delegation(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(
        workspace,
        runtime_id="dsh",
        model="deepseek-chat",
        extras={"dsh_profile": "epic-implement"},
    )

    with patch("loop.runner.session.execute_session") as mock_exec,          patch.object(DshAdapter, "resolve_binary", return_value=["/usr/bin/dsh"]),          patch.object(DshAdapter, "ensure_profiles", return_value=RuntimePreparationResult(ok=True)):
        mock_exec.return_value = SessionExecutionResult(
            exit_code=0,
            log_file=req.log_file,
            interrupted=False,
        )

        res = invoker.invoke(req)

        assert res.exit_code == 0
        assert res.runtime_id == "dsh"

        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == workspace["project_root"]
        assert kwargs["progress_mode"] == "stream_bytes"
        assert kwargs["stdin_text"] is None
        assert kwargs["command"][:3] == ["/usr/bin/dsh", "--profile", "epic-implement"]
        assert kwargs["stream_filter_cmd"] == [
            sys.executable,
            str(workspace["hub_root"] / "harness" / "hooks" / "dsh_stream_filter.py"),
        ]


def test_invoke_providers_codex_delegation(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="codex", model="gpt-5.6-turbo")

    with patch("loop.runner.session.execute_session") as mock_exec,          patch.object(CodexAdapter, "resolve_binary", return_value="/usr/bin/codex"), patch("loop.runtime_adapters.codex._resolve_codex_binary", return_value="/usr/bin/codex"):
        mock_exec.return_value = SessionExecutionResult(
            exit_code=0,
            log_file=req.log_file,
            interrupted=False,
        )

        res = invoker.invoke(req)

        assert res.exit_code == 0
        assert res.runtime_id == "codex"

        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == workspace["project_root"]
        assert kwargs["progress_mode"] == "codex_json"
        assert kwargs["stdin_text"] == "Test prompt for session"
        assert kwargs["command"][0] == "/usr/bin/codex"
        assert "exec" in kwargs["command"]
        assert "--cd" in kwargs["command"]
        assert kwargs["stream_filter_cmd"] == [
            sys.executable,
            str(workspace["hub_root"] / "harness" / "hooks" / "epic_codex_stream_filter.py"),
        ]


def test_invoke_providers_no_provider_specific_if_chains(workspace: dict[str, Path]):
    """Custom runtime adapter demonstrates pure protocol polymorphism with zero provider branches."""

    class CustomRuntimeAdapter(RuntimeAdapter):
        def resolve_working_directory(self, project_root: Path, hub_root: Path, ctx: SessionContext | None = None) -> Path:
            return project_root / "custom_sub"

        def requires_stdin_prompt(self, mode: str = "headless") -> bool:
            return True

        def progress_mode(self) -> str:
            return "custom_events"

        def resolve_stream_filter(self, hub_root: Path) -> list[str] | None:
            return ["custom_filter"]

        def prepare_runtime(self, hub_root: Path, project_root: Path, extras: dict[str, Any] | None = None) -> RuntimePreparationResult:
            return RuntimePreparationResult(ok=True)

        def build_command(self, ctx: SessionContext) -> list[str]:
            return ["custom-runtime-cli", "--run", ctx.prompt]

        def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
            return SessionAnalysis()

        def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
            return {}

        def collaboration_block(self, ctx: SessionContext) -> str:
            return ""

    invoker = SessionInvoker(adapter_factory=lambda rid: CustomRuntimeAdapter())
    req = _make_request(workspace, runtime_id="custom_ai")

    with patch("loop.runner.session.execute_session") as mock_exec:
        mock_exec.return_value = SessionExecutionResult(exit_code=0, log_file=req.log_file)

        res = invoker.invoke(req)

        assert res.exit_code == 0
        assert res.runtime_id == "custom_ai"
        mock_exec.assert_called_once()
        _, kwargs = mock_exec.call_args
        assert kwargs["cwd"] == workspace["project_root"] / "custom_sub"
        assert kwargs["progress_mode"] == "custom_events"
        assert kwargs["stdin_text"] == "Test prompt for session"
        assert kwargs["stream_filter_cmd"] == ["custom_filter"]
        assert kwargs["command"] == ["custom-runtime-cli", "--run", "Test prompt for session"]


# ============================================================================
# CP2: test_resilience_integration
# ============================================================================

def test_resilience_integration_timeout(workspace: dict[str, Path]):
    """Preserves subprocess timeout and writes timeout marker."""
    invoker = SessionInvoker()
    req = SessionRequest(
        session_id="timeout-1",
        prompt_file=workspace["prompt_file"],
        runtime_id="claude",
        phase="IMPLEMENT",
        model=None,
        mode="headless",
        log_file=workspace["log_file"],
        timeout_sec=1,
        kill_grace_sec=1,
        heartbeat_sec=None,
        idle_timeout_sec=None,
        permission_mode="dangerously-skip-permissions",
        extra_args=(),
        project_root=workspace["project_root"],
        hub_root=workspace["hub_root"],
    )

    # Command sleeps for 10 seconds, timeout is 1 sec
    sleep_cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    with patch.object(ClaudeAdapter, "prepare_runtime", return_value=RuntimePreparationResult(ok=True)),          patch.object(ClaudeAdapter, "build_command", return_value=sleep_cmd),          patch.object(ClaudeAdapter, "resolve_stream_filter", return_value=None):
        res = invoker.invoke(req)

        assert res.exit_code == 124
        assert res.interrupted is True
        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "SESSION_START" in log_content
        assert "SESSION_TIMEOUT" in log_content
        assert "SESSION_END" in log_content


def test_resilience_integration_log_writing_and_clean_exit(workspace: dict[str, Path]):
    """Preserves subprocess stdout logging and clean return code."""
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="claude")

    echo_cmd = [sys.executable, "-c", "import sys; sys.stdout.write('hello from subprocess' + chr(10))"]
    with patch.object(ClaudeAdapter, "prepare_runtime", return_value=RuntimePreparationResult(ok=True)),          patch.object(ClaudeAdapter, "build_command", return_value=echo_cmd),          patch.object(ClaudeAdapter, "resolve_stream_filter", return_value=None):
        res = invoker.invoke(req)

        assert res.exit_code == 0
        assert res.interrupted is False
        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "SESSION_START" in log_content
        assert "hello from subprocess" in log_content
        assert "SESSION_END session=test-1 exit_code=0" in log_content


def test_resilience_integration_idle_watchdog(workspace: dict[str, Path]):
    """Preserves idle timeout watchdog when process produces no progress."""
    invoker = SessionInvoker()
    req = SessionRequest(
        session_id="idle-1",
        prompt_file=workspace["prompt_file"],
        runtime_id="claude",
        phase="IMPLEMENT",
        model=None,
        mode="headless",
        log_file=workspace["log_file"],
        timeout_sec=10,
        kill_grace_sec=1,
        heartbeat_sec=None,
        idle_timeout_sec=1,
        permission_mode="dangerously-skip-permissions",
        extra_args=(),
        project_root=workspace["project_root"],
        hub_root=workspace["hub_root"],
    )

    # Process sleeps without writing anything -> idle watchdog should kill it
    hang_cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    with patch.object(ClaudeAdapter, "prepare_runtime", return_value=RuntimePreparationResult(ok=True)),          patch.object(ClaudeAdapter, "build_command", return_value=hang_cmd),          patch.object(ClaudeAdapter, "resolve_stream_filter", return_value=None):
        res = invoker.invoke(req)

        assert res.exit_code == 124
        assert res.interrupted is True
        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "SESSION_START" in log_content
        assert "SESSION_IDLE_TIMEOUT" in log_content


# ============================================================================
# CP3: test_fail_closed
# ============================================================================

def test_fail_closed_unknown_runtime_exits_fail_closed_no_claude_fallback(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="unknown_provider_xyz")

    with patch.object(ClaudeAdapter, "build_command") as mock_claude_build:
        res = invoker.invoke(req)

        assert res.exit_code == 2
        assert res.runtime_id == "unknown_provider_xyz"
        assert res.interrupted is False
        mock_claude_build.assert_not_called()

        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "unknown or invalid runtime 'unknown_provider_xyz'" in log_content


def test_fail_closed_missing_dsh_binary(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="dsh")

    with patch.object(DshAdapter, "resolve_binary", return_value=None),          patch.object(ClaudeAdapter, "build_command") as mock_claude_build:
        res = invoker.invoke(req)

        assert res.exit_code == 127
        assert res.runtime_id == "dsh"
        mock_claude_build.assert_not_called()

        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "dsh binary not found" in log_content


def test_fail_closed_invalid_dsh_profile(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(
        workspace,
        runtime_id="dsh",
        extras={"dsh_profile": "nonexistent-invalid-profile-xyz"},
    )

    with patch.object(DshAdapter, "resolve_binary", return_value=["/usr/bin/dsh"]),          patch.object(DshAdapter, "validate_profile", return_value=False),          patch.object(ClaudeAdapter, "build_command") as mock_claude_build:
        res = invoker.invoke(req)

        assert res.exit_code == 127
        assert res.runtime_id == "dsh"
        mock_claude_build.assert_not_called()

        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "invalid dsh profile" in log_content


def test_fail_closed_missing_codex_binary(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = _make_request(workspace, runtime_id="codex")

    with patch.object(CodexAdapter, "resolve_binary", return_value=None),          patch.object(ClaudeAdapter, "build_command") as mock_claude_build:
        res = invoker.invoke(req)

        assert res.exit_code == 127
        assert res.runtime_id == "codex"
        mock_claude_build.assert_not_called()

        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "codex binary not found" in log_content


def test_fail_closed_unreadable_prompt_file(workspace: dict[str, Path]):
    invoker = SessionInvoker()
    req = SessionRequest(
        session_id="unreadable-prompt",
        prompt_file=workspace["state_dir"] / "nonexistent_prompt.txt",
        runtime_id="claude",
        phase="IMPLEMENT",
        model=None,
        mode="headless",
        log_file=workspace["log_file"],
        timeout_sec=30,
        kill_grace_sec=5,
        heartbeat_sec=None,
        idle_timeout_sec=None,
        permission_mode="dangerously-skip-permissions",
        extra_args=(),
        project_root=workspace["project_root"],
        hub_root=workspace["hub_root"],
    )

    with patch.object(ClaudeAdapter, "resolve_binary", return_value="claude"):
        res = invoker.invoke(req)

        assert res.exit_code == 1
        assert res.runtime_id == "claude"
        log_content = workspace["log_file"].read_text(encoding="utf-8")
        assert "cannot read prompt file" in log_content
