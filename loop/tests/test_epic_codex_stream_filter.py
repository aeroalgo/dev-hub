from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import epic_codex_stream_filter as csf  # noqa: E402


def _capture_lines(lines: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        for line in lines:
            line = line.strip()
            if not line:
                continue
            csf.emit_from_obj(json.loads(line))
    return buf.getvalue()


def test_command_execution_shows_exec_not_output() -> None:
    lines = [
        json.dumps(
            {
                "type": "item.started",
                "item": {
                    "id": "item_3",
                    "type": "command_execution",
                    "command": "/bin/bash -lc \"sed -n '1,5p' harness/hooks/session_resilience.py\"",
                    "status": "in_progress",
                },
            }
        ),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_3",
                    "type": "command_execution",
                    "command": "/bin/bash -lc \"sed -n '1,5p' harness/hooks/session_resilience.py\"",
                    "aggregated_output": "#!/usr/bin/env python3\n\"\"\"secret\"\"\"\n",
                    "exit_code": 0,
                    "status": "completed",
                },
            }
        ),
    ]
    out = _capture_lines(lines)
    assert "exec\n" in out
    assert "sed -n '1,5p'" in out
    assert " succeeded\n" in out
    assert "secret" not in out
    assert "#!/usr/bin/env python3" not in out


def test_agent_message_with_code_fence_is_hidden() -> None:
    lines = [
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_4",
                    "type": "agent_message",
                    "text": "```python\nprint('x')\n```",
                },
            }
        )
    ]
    out = _capture_lines(lines)
    assert out == ""


def test_agent_message_plain_text_is_shown() -> None:
    lines = [
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_2",
                    "type": "agent_message",
                    "text": "Done.",
                },
            }
        )
    ]
    out = _capture_lines(lines)
    assert out == "Done.\n"


def test_skill_budget_warning_is_hidden() -> None:
    lines = [
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_1",
                    "type": "error",
                    "message": "Skill descriptions were shortened to fit the skills context budget.",
                },
            }
        )
    ]
    out = _capture_lines(lines)
    assert out == ""
