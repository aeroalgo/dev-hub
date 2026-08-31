"""Unit tests for bash-output-cap.py structured path integration and rendering."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add .claude/hooks directory to sys.path
HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import bash_output_cap
from llm_structured import LogError, LogSummary


def test_build_view_structured_failed_tests_in_view():
    summary = LogSummary(
        exit_code=1,
        failed_tests=["tests/test_foo.py::test_bar"],
        errors=[LogError(location="foo.py:10", message="AssertionError")],
        root_cause="Expected 1 got 2",
        summary_bullets=["Test failed due to mismatch"],
    )
    dump_path = Path("/tmp/dump.log")
    view = bash_output_cap.build_view_structured(summary, dump_path)
    assert "## Failed tests" in view
    assert "tests/test_foo.py::test_bar" in view
    assert "## Errors" in view
    assert "foo.py:10: AssertionError" in view
    assert "Root cause: Expected 1 got 2" in view
    assert "Test failed due to mismatch" in view


def test_build_view_structured_mode_label():
    summary = LogSummary(
        exit_code=1,
        failed_tests=["tests/test_foo.py::test_bar"],
        root_cause="Failed",
        summary_bullets=["Bullet 1"],
    )
    dump_path = Path("/tmp/dump.log")
    with (
        patch("bash_output_cap.extract_signals", return_value=("", False)),
        patch("bash_output_cap._llm_enabled", return_value=True),
        patch("bash_output_cap.run_log_summary", return_value=summary),
        patch.dict("os.environ", {"PROJECT_OUTPUT_SUMMARY_STRUCTURED": "1"}),
    ):
        view, mode = bash_output_cap.build_view("pytest", "some log line\n" * 500, dump_path)
        assert mode == "structured"
        assert "## Failed tests" in view


def test_structured_flag_zero_uses_head_tail():
    dump_path = Path("/tmp/dump.log")
    with (
        patch("bash_output_cap.extract_signals", return_value=("", False)),
        patch("bash_output_cap._llm_enabled", return_value=True),
        patch("bash_output_cap.run_log_summary") as mock_run_structured,
        patch.dict("os.environ", {"PROJECT_OUTPUT_SUMMARY_STRUCTURED": "0"}),
    ):
        view, mode = bash_output_cap.build_view("pytest", "some log line\n" * 500, dump_path)
        assert mode == "head-tail"
        assert "[output-cap:head-tail]" in view
        mock_run_structured.assert_not_called()


def test_structured_import_error_falls_back_to_head_tail():
    dump_path = Path("/tmp/dump.log")
    with (
        patch("bash_output_cap.extract_signals", return_value=("", False)),
        patch("bash_output_cap._llm_enabled", return_value=True),
        patch("bash_output_cap._HAS_STRUCTURED", False),
    ):
        view, mode = bash_output_cap.build_view("pytest", "some log line\n" * 500, dump_path)
        assert mode == "head-tail"
        assert "[output-cap:head-tail]" in view
