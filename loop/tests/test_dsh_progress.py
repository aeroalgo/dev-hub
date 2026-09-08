from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "dsh" / "plugins" / "epic-gate" / "lib" / "session-progress.js"


def _format(event: dict[str, object]) -> str:
    script = (
        "import { formatSessionProgress } from "
        f"{json.dumps(PLUGIN.as_uri())}; "
        f"process.stdout.write(formatSessionProgress({json.dumps(event)}) ?? '');"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_dsh_progress_formats_llm_step_and_tool_call() -> None:
    assert _format({"type": "step/start", "data": {"turn": 1, "step": 2}}) == (
        "==> dsh: LLM request turn=1 step=2\n"
    )
    assert _format(
        {
            "type": "tool/call",
            "data": {
                "turn": 1,
                "step": 2,
                "name": "Bash",
                "arguments": '{"command":"pytest loop/tests/test_dsh_progress.py"}',
            },
        }
    ) == "==> dsh: Bash pytest loop/tests/test_dsh_progress.py\n"
    assert _format({"type": "assistant/chunk", "data": {"turn": 1, "step": 2}}) == (
        "==> dsh: LLM streaming turn=1 step=2\n"
    )


def test_dsh_progress_formats_subagent_call_without_leaking_prompt() -> None:
    output = _format(
        {
            "type": "tool/call",
            "data": {
                "name": "Agent",
                "arguments": '{"subagent_type":"verify","prompt":"secret details"}',
            },
        }
    )
    assert output == "==> dsh: Agent verify\n"
    assert "secret details" not in output


def test_dsh_uses_stream_progress_for_idle_watchdog() -> None:
    loop = (ROOT / "loop" / "loop.sh").read_text(encoding="utf-8")
    dsh_branch = loop.split('elif [[ "$runtime_id" == "dsh" ]]', 1)[1].split("else", 1)[0]
    assert 'progress_mode="stream_bytes"' in dsh_branch
