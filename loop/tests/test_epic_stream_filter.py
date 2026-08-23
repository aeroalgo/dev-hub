from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import epic_stream_filter as esf  # noqa: E402


def _capture(objs: list[dict]) -> str:
    esf.reset_stream_state()
    buf = io.StringIO()
    with redirect_stdout(buf):
        for obj in objs:
            esf.emit_from_obj(obj)
    return buf.getvalue()


def test_stream_deltas_plus_assistant_do_not_double_text() -> None:
    full = (
        "Завершён atomic шаг **BACK IMPLEMENT s04**:\n"
        "- Suite: 58 passed.\n"
        "Модель ИИ: GPT"
    )
    events = [
        {"type": "stream_event", "event": {"type": "message_start"}},
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": full[:40]},
            },
        },
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": full[40:]},
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": full}]},
        },
    ]
    out = _capture(events)
    assert out == full
    assert out.count("Завершён atomic шаг") == 1
    assert out.count("Модель ИИ: GPT") == 1


def test_assistant_only_still_emits_text() -> None:
    text = "Handoff: s04 done.\nМодель ИИ: GPT"
    out = _capture(
        [{"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}]
    )
    assert out == text


def test_assistant_tools_still_emit_when_text_streamed() -> None:
    events = [
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "ok"},
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "ok"},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "Read",
                        "input": {"file_path": "memory-bank/activeContext.md"},
                    },
                ]
            },
        },
    ]
    out = _capture(events)
    assert out.startswith("ok")
    assert "→ Read memory-bank/activeContext.md" in out
    assert out.count("ok") == 1


def test_main_stdin_pipeline_no_double() -> None:
    esf.reset_stream_state()
    full = "one line finish\nМодель ИИ: GPT"
    lines = [
        json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": full},
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": full}]},
            }
        ),
    ]
    stdin = io.StringIO("\n".join(lines) + "\n")
    buf = io.StringIO()
    old_stdin = sys.stdin
    try:
        sys.stdin = stdin
        with redirect_stdout(buf):
            esf.main()
    finally:
        sys.stdin = old_stdin
    out = buf.getvalue()
    assert out.count(full) == 1
    assert "--- epic stream end ---" in out


def test_lowercase_read_prints_path() -> None:
    """Gemini/omniroute may emit tool name 'read' instead of 'Read'."""
    out = _capture(
        [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_1",
                            "name": "read",
                            "input": {
                                "file_path": "/home/aero/PyProject/job-autopilot/memory-bank/activeContext.md"
                            },
                        }
                    ]
                },
            }
        ]
    )
    assert "→ Read activeContext.md" in out
    assert out.strip() != "→ read"


def test_empty_input_on_content_block_start_does_not_block_path() -> None:
    """Empty input {} must not print bare → Read and skip the later full block."""
    out = _capture(
        [
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "Read",
                        "input": {},
                    },
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_1",
                            "name": "Read",
                            "input": {"file_path": "memory-bank/activeContext.md"},
                        }
                    ]
                },
            },
        ]
    )
    assert "→ Read memory-bank/activeContext.md" in out
    assert "→ Read\n" not in out
    assert out.count("→ Read") == 1


def test_message_delta_usage_printed_once() -> None:
    out = _capture(
        [
            {
                "type": "stream_event",
                "event": {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {
                        "input_tokens": 25568,
                        "output_tokens": 498,
                        "cache_read_input_tokens": 20384,
                    },
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {
                        "input_tokens": 25568,
                        "output_tokens": 498,
                        "cache_read_input_tokens": 20384,
                    },
                },
            },
            {
                "type": "stream_event",
                "event": {
                    "type": "message_delta",
                    "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                    "usage": {"input_tokens": 26000, "output_tokens": 100},
                },
            },
        ]
    )
    assert out.count("↻ tokens in=25568 out=498 cache_read=20384") == 1
    assert "↻ tokens in=26000 out=100" in out
