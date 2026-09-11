from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from loop.runtime_adapters.base import (
    RuntimeAdapter,
    RuntimePreparationResult,
    SessionAnalysis,
    SessionContext,
)


class ClaudeAdapter(RuntimeAdapter):
    """RuntimeAdapter implementation for Claude CLI."""

    def resolve_binary(self, hub_root: Path | None = None) -> str | None:
        bin_env = os.environ.get("CLAUDE_PATH") or os.environ.get("CLAUDE")
        if bin_env and os.access(bin_env, os.X_OK):
            return bin_env
        which_path = shutil.which("claude")
        if which_path:
            return which_path
        if bin_env:
            return bin_env
        return None

    def resolve_working_directory(
        self,
        project_root: Path,
        hub_root: Path,
        ctx: SessionContext | None = None,
    ) -> Path:
        return Path(hub_root)

    def requires_stdin_prompt(self, mode: str = "headless") -> bool:
        return False

    def progress_mode(self) -> str:
        return "tool_json"

    def resolve_stream_filter(self, hub_root: Path) -> list[str] | None:
        filter_path = Path(hub_root) / "harness" / "hooks" / "epic_stream_filter.py"
        if filter_path.exists():
            return [sys.executable, str(filter_path)]
        return None

    def prepare_runtime(
        self,
        hub_root: Path,
        project_root: Path,
        extras: dict[str, Any] | None = None,
    ) -> RuntimePreparationResult:
        claude_bin = self.resolve_binary(hub_root)
        if not claude_bin:
            return RuntimePreparationResult(
                ok=False,
                exit_code=127,
                error="claude binary not found; install @anthropic-ai/claude-code or set CLAUDE_PATH",
            )
        return RuntimePreparationResult(ok=True, command=[claude_bin])

    def build_command(self, ctx: SessionContext) -> list[str]:
        claude_bin = ctx.extras.get("claude_bin") or "claude"
        mode = ctx.extras.get("mode", "headless")
        project_root = ctx.extras.get("project_root")

        if mode == "headless":
            cmd = [
                claude_bin,
                "-p",
                ctx.prompt,
                "--output-format",
                "stream-json",
                "--include-partial-messages",
                "--verbose",
            ]
        else:
            cmd = [claude_bin, ctx.prompt]

        if project_root:
            cmd.extend(["--add-dir", str(project_root)])

        perm_mode = ctx.extras.get("permission_mode")
        if perm_mode:
            if perm_mode in ("dangerously-skip-permissions", "--dangerously-skip-permissions"):
                cmd.append("--dangerously-skip-permissions")
            elif perm_mode.startswith("-"):
                cmd.append(perm_mode)

        if ctx.model:
            cmd.extend(["--model", ctx.model])

        extra_args = ctx.extras.get("extra_args")
        if extra_args:
            if isinstance(extra_args, (list, tuple)):
                cmd.extend(list(extra_args))

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

    def ownership_expected_step(self, state: dict[str, Any]) -> str:
        from loop.session_finalize import ownership_expected_step

        return ownership_expected_step(state)

    def apply_ownership_identity(self, identity: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from loop.session_finalize import apply_ownership_identity

        return apply_ownership_identity(identity, state)

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
