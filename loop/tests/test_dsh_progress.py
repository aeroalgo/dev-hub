from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "dsh" / "plugins" / "epic-gate" / "lib" / "session-progress.js"
COMPAT_PLUGIN = ROOT / "dsh" / "plugins" / "epic-gate" / "lib" / "tool-name-compat.js"
STANDALONE_COMPAT_PLUGIN = ROOT / "dsh" / "plugins" / "tool-name-compat" / "src" / "index.js"


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


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


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


def test_dsh_progress_reports_tool_failure_and_preserves_tool_name() -> None:
    output = _format(
        {
            "type": "tool/result",
            "data": {
                "turn": 1,
                "step": 2,
                "message": {
                    "source": {"kind": "tool", "callId": "call-1"},
                    "content": [
                        {
                            "type": "tool-result",
                            "content": [
                                {"type": "text", "text": 'Error: unknown tool "Read"'}
                            ],
                            "isError": True,
                        }
                    ],
                },
                "error": {"name": "ToolNotFoundError", "code": "UNKNOWN_TOOL"},
                "name": "Read",
            },
        }
    )
    assert output == (
        '==> dsh: tool failed name=Read call=call-1 '
        'error=Error: unknown tool "Read"\n'
    )


def test_dsh_progress_describes_legacy_editor_operation() -> None:
    output = _format(
        {
            "type": "tool/call",
            "data": {
                "turn": 1,
                "step": 2,
                "name": "str_replace_editor",
                "arguments": '{"command":"view","path":"/repo/AGENTS.md"}',
            },
        }
    )
    assert output == "==> dsh: str_replace_editor view /repo/AGENTS.md\n"


def test_dsh_registers_claude_filesystem_aliases_against_native_tools() -> None:
    script = """
        import { applyToolNameCompatibility } from __PLUGIN__;
        const registrations = new Map();
        const sections = [];
        const native = (name) => ({
            name,
            parameters: name === 'bash'
                ? { command: { type: 'string', required: true }, description: { type: 'string', required: true } }
                : { file_path: { type: 'string', required: true } },
            output: { schema: { type: 'object' }, render: () => [] },
            async execute(args) { return args; },
        });
        for (const name of ['read', 'write', 'edit', 'bash', 'glob', 'grep']) registrations.set(name, native(name));
        const ctx = {
            tools: {
                get(name) { return registrations.get(name); },
                register(definition) { registrations.set(definition.name, definition); return () => registrations.delete(definition.name); },
            },
            systemPrompt: { section(value) { sections.push(value); } },
        };
        applyToolNameCompatibility(ctx);
        const read = registrations.get('Read');
        const bash = registrations.get('Bash');
        const result = await read.execute({ file_path: 'AGENTS.md' }, {});
        const bashResult = await bash.execute({ command: 'pytest' }, {});
        process.stdout.write(JSON.stringify({ names: [...registrations.keys()], result, bashResult, sections }));
    """.replace("__PLUGIN__", json.dumps(COMPAT_PLUGIN.as_uri()))
    proc = _run_node(script)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["result"] == {"file_path": "AGENTS.md"}
    assert result["bashResult"] == {"command": "pytest", "description": "Run command: pytest"}
    assert {"Read", "Write", "Edit", "Bash", "Glob", "Grep"} <= set(result["names"])
    assert "lowercase" in result["sections"][0]["text"]


def test_standalone_compat_plugin_registers_claude_tool_aliases() -> None:
    script = """
        import { apply } from __PLUGIN__;
        const registrations = new Map();
        const native = (name) => ({
            name,
            parameters: { file_path: { type: 'string', required: true } },
            output: { schema: { type: 'object' }, render: () => [] },
            async execute(args) { return { name, args }; },
        });
        for (const name of ['read', 'write', 'edit', 'bash', 'glob', 'grep']) registrations.set(name, native(name));
        const ctx = {
            tools: {
                get(name) { return registrations.get(name); },
                register(definition) { registrations.set(definition.name, definition); return () => registrations.delete(definition.name); },
            },
            systemPrompt: { section() {} },
        };
        await apply(ctx);
        const result = await registrations.get('Read').execute({ file_path: 'AGENTS.md' }, {});
        process.stdout.write(JSON.stringify({ names: [...registrations.keys()], result }));
    """.replace("__PLUGIN__", json.dumps(STANDALONE_COMPAT_PLUGIN.as_uri()))
    proc = _run_node(script)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["result"] == {"name": "read", "args": {"file_path": "AGENTS.md"}}
    assert {"Read", "Write", "Edit", "Bash", "Glob", "Grep"} <= set(result["names"])


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
