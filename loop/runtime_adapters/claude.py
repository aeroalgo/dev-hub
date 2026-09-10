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

    def collaboration_block(self, ctx: SessionContext) -> str:
        from loop.runtime_adapters.collaboration import claude_collaboration_block
        return claude_collaboration_block(ctx)

    def subagent_lifecycle(self, cwd: Any, session_id: str) -> Any:
        from loop.runtime_adapters.subagent_lifecycle import SubagentLifecycle

        return SubagentLifecycle(cwd, session_id, "claude")

    def parse_session_events(self, raw_log: str, ctx: SessionContext) -> Any:
        from loop.runtime.session_events import parse_session_events
        return parse_session_events(raw_log, ctx.runtime_id)

    def post_session(self, cwd: Any, log_path: Any, ctx: SessionContext) -> list[dict[str, Any]]:
        return []

    def resolve_session_close_identity(self, state: dict[str, Any]) -> Any:
        from loop.session_finalize import resolve_session_close_identity

        return resolve_session_close_identity(state)

    def should_probe_analyze_promotion(self, *, armed_step: Any, active_context_text: str | None = None) -> bool:
        from loop.session_finalize import should_probe_analyze_promotion

        return should_probe_analyze_promotion(
            armed_step=armed_step,
            active_context_text=active_context_text,
        )


    def normalize_read_event(self, payload: dict[str, Any], cwd: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import normalize_read_payload
        return normalize_read_payload(payload, provider="claude", default_cwd=cwd)

    def normalize_write_event(self, payload: dict[str, Any], cwd: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import normalize_write_payload
        return normalize_write_payload(payload, provider="claude", default_cwd=cwd)

    def evaluate_context_read(self, payload: dict[str, Any], cwd: Any = None, runtime_dir: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import evaluate_read_payload
        return evaluate_read_payload(payload, provider="claude", cwd=cwd, runtime_dir=runtime_dir)

    def evaluate_context_write(self, payload: dict[str, Any], cwd: Any = None, runtime_dir: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import evaluate_write_payload
        return evaluate_write_payload(payload, provider="claude", cwd=cwd, runtime_dir=runtime_dir)
