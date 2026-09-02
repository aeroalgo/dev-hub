import os
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch
from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext
from loop.runtime_adapters.codex import CodexAdapter

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_codex_adapter_implements_protocol():
    adapter = CodexAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_build_command_contains_exec():
    adapter = CodexAdapter()
    ctx = SessionContext(prompt="do task", phase="implement")
    with patch("loop.runtime_adapters.codex._resolve_codex_binary", return_value="codex"):
        cmd = adapter.build_command(ctx)
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    assert "--json" in cmd
    assert "--ephemeral" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--cd" in cmd


def test_build_command_no_model_when_none():
    adapter = CodexAdapter()
    ctx = SessionContext(prompt="do task", phase="implement", model=None)
    with patch("loop.runtime_adapters.codex._resolve_codex_binary", return_value="codex"):
        cmd = adapter.build_command(ctx)
    assert "--model" not in cmd


def test_build_command_with_model():
    adapter = CodexAdapter()
    ctx = SessionContext(prompt="do task", phase="implement", model="gpt-4o")
    with patch("loop.runtime_adapters.codex._resolve_codex_binary", return_value="codex"):
        cmd = adapter.build_command(ctx)
    assert "--model" in cmd
    assert "gpt-4o" in cmd


def test_build_command_adds_omniroute_provider_when_configured(tmp_path, monkeypatch):
    adapter = CodexAdapter()
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / ".omniroute_key").write_text("sk-test", encoding="utf-8")
    (codex_home / "config.toml").write_text(
        'model_provider = "omniroute"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    ctx = SessionContext(
        prompt="do task",
        phase="implement",
        model="cx/gpt-5.6-luna-xhigh",
    )
    wrap = "/path/to/codex-omniroute.sh"
    with patch("loop.runtime_adapters.codex._resolve_codex_binary", return_value=wrap):
        cmd = adapter.build_command(ctx)
    assert '-c' in cmd
    assert 'model_provider="omniroute"' in cmd
    assert "--model" in cmd
    assert "cx/gpt-5.6-luna-xhigh" in cmd


def test_missing_binary_raises_exit127():
    adapter = CodexAdapter()
    ctx = SessionContext(prompt="do task", phase="implement")
    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=False), \
         patch.dict(os.environ, {}, clear=True), \
         patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(SystemExit) as exc_info:
            adapter.build_command(ctx)
        assert exc_info.value.code == 127


def test_no_silent_claude_fallback():
    adapter = CodexAdapter()
    ctx = SessionContext(prompt="do task", phase="implement")
    with patch("loop.runtime_adapters.codex._resolve_codex_binary", side_effect=SystemExit(127)):
        with pytest.raises(SystemExit) as exc_info:
            adapter.build_command(ctx)
        assert exc_info.value.code == 127


def test_analyze_completed_fixture():
    adapter = CodexAdapter()
    raw_log = (FIXTURES_DIR / "codex_session_completed.log").read_text(encoding="utf-8")
    ctx = SessionContext(prompt="do task", phase="implement", extras={"exit_code": 0})
    analysis = adapter.analyze_log(raw_log, ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.retry is False
    assert analysis.reason is None


def test_analyze_aborted_fixture():
    adapter = CodexAdapter()
    raw_log = (FIXTURES_DIR / "codex_session_aborted.log").read_text(encoding="utf-8")
    ctx = SessionContext(prompt="do task", phase="implement", extras={"exit_code": 1})
    analysis = adapter.analyze_log(raw_log, ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.retry is True
    assert analysis.reason == "aborted"


def test_analyze_exit0_aborted_in_agent_prose_not_abort():
    adapter = CodexAdapter()
    raw_log = (
        "SESSION_START session=1 mode=headless command=codex\n"
        '{"type":"item.completed","item":{"type":"agent_message","text":"prev_session: aborted — retry"}}\n'
        '{"type":"item.completed","item":{"type":"command_execution","aggregated_output":'
        '"if last.get(\\"status\\") == \\"aborted\\":\\n","exit_code":0,"status":"completed"}}\n'
        "SESSION_END session=1 exit_code=0 elapsed=100.0s\n"
    )
    ctx = SessionContext(prompt="do task", phase="implement", extras={"exit_code": 0})
    analysis = adapter.analyze_log(raw_log, ctx)
    assert analysis.reason is None
    assert analysis.retry is False


def test_analyze_auth_fail_fixture():
    adapter = CodexAdapter()
    raw_log = (FIXTURES_DIR / "codex_session_auth_fail.log").read_text(encoding="utf-8")
    ctx = SessionContext(prompt="do task", phase="implement", extras={"exit_code": 1})
    analysis = adapter.analyze_log(raw_log, ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.retry is False
    assert analysis.reason == "auth_failed"


def test_analyze_log_binary_missing_fixture():
    adapter = CodexAdapter()
    raw_log = (FIXTURES_DIR / "codex_session_binary_missing.log").read_text(encoding="utf-8")
    ctx = SessionContext(prompt="do task", phase="implement", extras={"exit_code": 127})
    analysis = adapter.analyze_log(raw_log, ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.retry is False
    assert analysis.reason == "command not found"


def test_which_codex_script():
    script_path = os.path.join(os.getcwd(), "codex/bin/which-codex.sh")
    assert os.path.exists(script_path)
    res = subprocess.run(["bash", script_path], capture_output=True, text=True)
    assert res.returncode in (0, 127)
