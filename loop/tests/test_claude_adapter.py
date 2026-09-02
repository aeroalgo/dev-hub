from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext
from loop.runtime_adapters.claude import ClaudeAdapter


def test_claude_adapter_implements_protocol():
    adapter = ClaudeAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_build_command_contains_binary_and_model():
    adapter = ClaudeAdapter()
    ctx = SessionContext(prompt="hello world", phase="implement", model="agy/claude-sonnet-4-6")
    cmd = adapter.build_command(ctx)
    assert isinstance(cmd, list)
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "hello world" in cmd
    assert "--model" in cmd
    assert "agy/claude-sonnet-4-6" in cmd

    # Test without model
    ctx_no_model = SessionContext(prompt="hello world", phase="implement")
    cmd_no_model = adapter.build_command(ctx_no_model)
    assert "--model" not in cmd_no_model


def test_prepare_extras_empty_dict():
    adapter = ClaudeAdapter()
    ctx = SessionContext(prompt="hello", phase="implement")
    assert adapter.prepare_extras(ctx) == {}


def test_analyze_log_passthrough_no_reason():
    adapter = ClaudeAdapter()
    ctx = SessionContext(prompt="hello", phase="implement")
    analysis = adapter.analyze_log("some raw log output", ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.reason is None
