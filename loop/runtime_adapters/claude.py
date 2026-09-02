from __future__ import annotations

from typing import Any

from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext


class ClaudeAdapter(RuntimeAdapter):
    """RuntimeAdapter implementation for Claude CLI."""

    def build_command(self, ctx: SessionContext) -> list[str]:
        cmd = ["claude", "-p", ctx.prompt, "--output-format", "stream-json", "--include-partial-messages", "--verbose"]
        if ctx.model:
            cmd.extend(["--model", ctx.model])
        return cmd

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        return SessionAnalysis(reason=None)

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {}
