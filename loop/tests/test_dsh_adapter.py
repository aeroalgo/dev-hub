from __future__ import annotations

from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext
from loop.runtime_adapters.dsh import DshAdapter


def test_dsh_adapter_implements_protocol():
    adapter = DshAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_prepare_extras_phase_mapping():
    adapter = DshAdapter()
    ctx = SessionContext(prompt="test", phase="implement")
    assert adapter.prepare_extras(ctx) == {"dsh_profile": "epic-implement"}

    ctx_uppercase = SessionContext(prompt="test", phase="DECOMPOSE")
    assert adapter.prepare_extras(ctx_uppercase) == {"dsh_profile": "epic-decompose"}


def test_analyze_log_mismatch_sets_reason():
    adapter = DshAdapter()
    ctx = SessionContext(prompt="test", phase="implement", model="claude-3-5-sonnet")
    raw_log = '{"requested_model": "claude-3-5-sonnet", "actual_model": "claude-3-haiku"}'
    analysis = adapter.analyze_log(raw_log, ctx)
    assert isinstance(analysis, SessionAnalysis)
    assert analysis.reason is not None
    assert "model_substitution" in analysis.reason
    assert "requested=claude-3-5-sonnet" in analysis.reason
    assert "actual=claude-3-haiku" in analysis.reason

    # Normal log without mismatch
    normal_log = '{"requested_model": "claude-3-5-sonnet", "actual_model": "claude-3-5-sonnet"}'
    analysis_normal = adapter.analyze_log(normal_log, ctx)
    assert analysis_normal.reason is None


def test_build_command_wraps_build_dsh_command():
    adapter = DshAdapter()
    ctx = SessionContext(prompt="do work", phase="implement", extras={"dsh_profile": "epic-custom"})
    cmd = adapter.build_command(ctx)
    assert cmd == ["dsh", "--profile", "epic-custom", "--no-open", "do work"]

    # Fallback to phase default if extras has no dsh_profile
    ctx_no_extra = SessionContext(prompt="do work", phase="implement")
    cmd_default = adapter.build_command(ctx_no_extra)
    assert cmd_default == ["dsh", "--profile", "epic-implement", "--no-open", "do work"]


def test_dsh_adapter_does_not_depend_on_standalone_functions():
    adapter = DshAdapter()
    ctx = SessionContext(prompt="hello", phase="implement")
    assert adapter.build_command(ctx) == ["dsh", "--profile", "epic-implement", "--no-open", "hello"]

