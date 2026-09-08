from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

import dsh_stream_filter as dsf  # noqa: E402


def test_compat_startup_noise_is_hidden() -> None:
    lines = [
        "⭐ dsh-claude-compat works for you?\n",
        "   Show some love: https://github.com/biedongbin/dsh-claude-compat\n",
        "dsh-claude-compat: SessionStart hook output: {\"additionalContext\": \"...\"}\n",
    ]
    output = io.StringIO()
    with redirect_stdout(output):
        for line in lines:
            if not dsf.is_noise(line):
                print(line, end="")
    assert output.getvalue() == ""


def test_regular_dsh_output_is_preserved() -> None:
    line = "{\"type\": \"session_end\", \"status\": \"completed\"}\n"
    output = io.StringIO()
    with redirect_stdout(output):
        if not dsf.is_noise(line):
            print(line, end="")
    assert output.getvalue() == line
