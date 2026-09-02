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
        exit_code = ctx.extras.get("exit_code")
        log_path = ctx.extras.get("log_path")
        expected_model = ctx.model
        reason = None
        if log_path is not None:
            from harness.hooks.session_resilience import detect_abort_in_log
            reason = detect_abort_in_log(
                log_path, exit_code=exit_code, expected_model=expected_model
            )
        return SessionAnalysis(reason=reason)

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {}
