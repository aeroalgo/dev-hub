from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import normalize_tool_name, read_stdin  # type: ignore


def test_normalize_tool_name_aliases() -> None:
    assert normalize_tool_name("bash") == "Bash"
    assert normalize_tool_name("shell") == "Bash"
    assert normalize_tool_name("Bash") == "Bash"
    assert normalize_tool_name("agent") == "Agent"
    assert normalize_tool_name("Agent") == "Agent"
    assert normalize_tool_name("task") == "Task"
    assert normalize_tool_name("Task") == "Task"
    assert normalize_tool_name("read") == "Read"
    assert normalize_tool_name("write") == "Write"
    assert normalize_tool_name("edit") == "Edit"
    assert normalize_tool_name("glob") == "Glob"
    assert normalize_tool_name("grep") == "Grep"


def test_normalize_tool_name_unknown_fail_closed(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = normalize_tool_name("unknown_tool_xyz")
        assert result == "unknown_tool_xyz"
        assert any("unknown tool_name" in record.message.lower() for record in caplog.records)


def test_read_stdin_normalizes_tool_name(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"tool_name": "bash", "tool_input": {"command": "echo 1"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    data = read_stdin()
    assert data["tool_name"] == "Bash"
