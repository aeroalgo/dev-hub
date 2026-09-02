from __future__ import annotations

from dataclasses import FrozenInstanceError
import pytest

from loop.runtime_adapters.base import (
    RuntimeAdapter,
    RuntimeCapabilities,
    SessionAnalysis,
    SessionContext,
)


class DummyValidAdapter:
    def build_command(self, ctx: SessionContext) -> list[str]:
        return ["echo", ctx.prompt]

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        return SessionAnalysis(reason=None, retry=False)

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {}


class DummyMissingMethodAdapter:
    def build_command(self, ctx: SessionContext) -> list[str]:
        return ["echo", ctx.prompt]

    # missing analyze_log and prepare_extras


def test_protocol_check():
    adapter = DummyValidAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_missing_method_fails_type_check():
    adapter = DummyMissingMethodAdapter()
    assert not isinstance(adapter, RuntimeAdapter)


def test_session_context_frozen_dataclass():
    ctx = SessionContext(prompt="test prompt", phase="IMPLEMENT", model="claude-3-5-sonnet")
    assert ctx.prompt == "test prompt"
    assert ctx.phase == "IMPLEMENT"
    assert ctx.model == "claude-3-5-sonnet"
    assert ctx.runtime_id == "claude"
    assert ctx.extras == {}

    with pytest.raises(FrozenInstanceError):
        ctx.prompt = "new prompt"  # type: ignore[misc]


def test_session_analysis_fields():
    analysis = SessionAnalysis(
        reason="error occurred",
        retry=True,
        dsh_abort_kind="transient",
        structured_output={"key": "val"},
    )
    assert analysis.reason == "error occurred"
    assert analysis.retry is True
    assert analysis.dsh_abort_kind == "transient"
    assert analysis.structured_output == {"key": "val"}

    default_analysis = SessionAnalysis()
    assert default_analysis.reason is None
    assert default_analysis.retry is False
    assert default_analysis.dsh_abort_kind is None
    assert default_analysis.structured_output is None
