"""Unit tests for llm_structured.py LogSummary, LogError, make_output_cap_agent, and run_log_summary."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add .claude/hooks directory to sys.path
HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import pytest
from pydantic import ValidationError
from llm_structured import LogError, LogSummary, make_output_cap_agent, run_log_summary


def test_log_error_location_empty_default():
    err = LogError(message="Syntax error")
    assert err.location == ""
    assert err.message == "Syntax error"


def test_log_summary_canonical_fixture():
    fixture_dict = {
        "exit_code": 1,
        "failed_tests": ["tests/test_foo.py::test_bar"],
        "errors": [{"location": "foo.py:10", "message": "AssertionError"}],
        "root_cause": "Expected 1 got 2",
        "summary_bullets": ["Test failed due to mismatch"],
    }
    summary = LogSummary(**fixture_dict)
    assert summary.exit_code == 1
    assert summary.failed_tests == ["tests/test_foo.py::test_bar"]
    assert len(summary.errors) == 1
    assert summary.errors[0].location == "foo.py:10"
    assert summary.errors[0].message == "AssertionError"
    assert summary.root_cause == "Expected 1 got 2"
    assert summary.summary_bullets == ["Test failed due to mismatch"]


def test_log_summary_max_length_rejected():
    too_many_tests = [f"test_{i}" for i in range(21)]
    with pytest.raises(ValidationError):
        LogSummary(failed_tests=too_many_tests)

    too_many_bullets = [f"bullet_{i}" for i in range(26)]
    with pytest.raises(ValidationError):
        LogSummary(summary_bullets=too_many_bullets)

    too_many_errors = [LogError(message=f"err_{i}") for i in range(31)]
    with pytest.raises(ValidationError):
        LogSummary(errors=too_many_errors)


def test_make_output_cap_agent_uses_env_url():
    custom_env = {
        "PROJECT_OUTPUT_SUMMARY_URL": "http://custom-host:8080/v1",
        "PROJECT_OUTPUT_SUMMARY_MODEL": "test-model",
        "PROJECT_OUTPUT_SUMMARY_KEY": "test-key-123",
    }
    with patch("llm_structured.OpenAIProvider") as mock_provider:
        agent = make_output_cap_agent("test-model", env=custom_env)
        assert agent is not None
        mock_provider.assert_called_once_with(
            base_url="http://custom-host:8080/v1",
            api_key="test-key-123",
        )


def test_run_log_summary_returns_none_on_network_fail():
    custom_env = {
        "PROJECT_OUTPUT_SUMMARY_KEY": "dummy",
        "PROJECT_OUTPUT_SUMMARY_RETRIES": "1",
    }
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(side_effect=ConnectionError("Network down"))

    with patch("llm_structured.make_output_cap_agent", return_value=mock_agent):
        res = run_log_summary("pytest", "error log", "/tmp/dump.log", env=custom_env)
        assert res is None


def test_run_log_summary_falls_back_to_fallback_model():
    custom_env = {
        "PROJECT_OUTPUT_SUMMARY_MODEL": "primary-model",
        "PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL": "fallback-model",
        "PROJECT_OUTPUT_SUMMARY_KEY": "dummy",
        "PROJECT_OUTPUT_SUMMARY_RETRIES": "1",
    }

    primary_agent = MagicMock()
    primary_agent.run = AsyncMock(side_effect=ConnectionError("Primary timeout"))

    fallback_agent = MagicMock()
    expected_summary = LogSummary(exit_code=1, root_cause="Fallback succeeded")
    mock_res = MagicMock()
    mock_res.data = expected_summary
    fallback_agent.run = AsyncMock(return_value=mock_res)

    def agent_factory(model=None, env=None):
        if model == "primary-model":
            return primary_agent
        return fallback_agent

    with patch("llm_structured.make_output_cap_agent", side_effect=agent_factory):
        res = run_log_summary("pytest", "error log", "/tmp/dump.log", env=custom_env)
        assert res is not None
        assert res.root_cause == "Fallback succeeded"


def test_run_log_summary_retries_on_validation_error():
    custom_env = {
        "PROJECT_OUTPUT_SUMMARY_KEY": "dummy",
        "PROJECT_OUTPUT_SUMMARY_RETRIES": "3",
    }

    mock_agent = MagicMock()
    expected_summary = LogSummary(exit_code=0, root_cause="Succeeded on retry 2")
    mock_res = MagicMock()
    mock_res.data = expected_summary

    calls = 0
    async def mock_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValidationError.from_exception_data("Validation failed", [])
        return mock_res

    mock_agent.run = AsyncMock(side_effect=mock_run)

    with patch("llm_structured.make_output_cap_agent", return_value=mock_agent):
        res = run_log_summary("pytest", "error log", "/tmp/dump.log", env=custom_env)
        assert res is not None
        assert res.root_cause == "Succeeded on retry 2"
        assert calls == 2


def test_summary_disabled_no_agent_call():
    custom_env = {
        "PROJECT_OUTPUT_SUMMARY": "0",
        "PROJECT_OUTPUT_SUMMARY_KEY": "dummy",
    }
    with patch("llm_structured.make_output_cap_agent") as mock_builder:
        res = run_log_summary("pytest", "error log", "/tmp/dump.log", env=custom_env)
        assert res is None
        mock_builder.assert_not_called()


@pytest.mark.skip(reason="FR-008 Integration stub for live OmniRoute network calls")
def test_live_omniroute_integration_stub():
    pass
