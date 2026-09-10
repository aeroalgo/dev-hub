import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from harness.hooks.session_resilience import detect_shell_command_not_found
from harness.hooks.session_resilience import COLLABORATION_WAIT_TIMEOUT_REASON
from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext

_CODEX_ABORT_RE = re.compile(
    r"(?i)(?:session aborted(?:\s+by\b|\s*$)|codex session aborted)"
)
_CODEX_UNSUPPORTED_TOOL_RE = re.compile(
    r"(?i)^\s*(?:ERROR\s+codex_core::tools::router:\s*error=unsupported call:\s*|"
    r"CODEX_UNSUPPORTED_TOOL_CALL\s+tool=)(?P<tool>[A-Za-z_][A-Za-z0-9_.:-]*)"
)
# Real Codex lines always carry ERROR / wrapper marker. Colon after "call" is
# mandatory; tool must start with letter/underscore so source dumps of this
# module (e.g. `unsupported call:\s*|`) never yield tool=":".
_CODEX_UNSUPPORTED_TOOL_LOOSE_RE = re.compile(
    r"(?i)(?:\bERROR\b|\bCODEX_UNSUPPORTED_TOOL_CALL\b)[^\n]*?"
    r"unsupported\s+call:\s*(?:tool=)?(?P<tool>[A-Za-z_][A-Za-z0-9_.:-]*)"
)
_CODEX_NATIVE_COLLAB_FEATURE = "multi_agent"
_CODEX_TRANSIENT_STATUS_RE = re.compile(
    r"(?i)\b(?:429|500|502|503|504)\b[^\n]*(?:service|server|gateway|capacity|temporarily|unavailable|error)"
)


def _detect_codex_unsupported_tool(raw_log: str) -> str | None:
    """Detect real Codex unsupported-tool failures (not agent command dumps).

    Claude abort detection does not grep child/bash stdout. Skip JSONL ``item.*``
    lines so reading this module's source into the session log cannot false-hit.
    """
    for line in raw_log.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                event_type = str(obj.get("type") or "")
                if event_type.startswith("item.") or event_type in {
                    "thread.started",
                    "turn.started",
                    "turn.completed",
                }:
                    continue
        match = _CODEX_UNSUPPORTED_TOOL_RE.search(stripped)
        if match:
            return match.group("tool")
        loose = _CODEX_UNSUPPORTED_TOOL_LOOSE_RE.search(stripped)
        if loose:
            return loose.group("tool")
    return None


def _codex_error_text(raw_log: str) -> str:
    """Extract runtime errors without treating command output as CLI errors."""
    errors: list[str] = []
    for line in raw_log.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            if not stripped.startswith(("SESSION_", "EXPECTED_MODEL ")):
                errors.append(stripped)
            continue
        if not isinstance(obj, dict):
            continue
        obj_type = obj.get("type")
        if obj_type == "error":
            for key in ("message", "error", "detail"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    errors.append(value.strip())
        elif obj_type == "item.completed":
            item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
            if item.get("type") == "error":
                for key in ("message", "error", "detail"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        errors.append(value.strip())
        elif obj_type == "result" and obj.get("is_error"):
            for key in ("result", "error", "message"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    errors.append(value.strip())
    return "\n".join(errors)


def _detect_codex_runtime_abort(raw_log: str) -> bool:
    for line in raw_log.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            if _CODEX_ABORT_RE.search(stripped):
                return True
            continue
        if not isinstance(obj, dict):
            continue
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        if obj.get("type") == "item.completed" and item.get("type") == "error":
            message = str(item.get("message") or "")
            if _CODEX_ABORT_RE.search(message):
                return True
    return False


def _resolve_codex_binary() -> str:
    """Locate codex binary using which-codex.sh or direct resolution.

    Raises SystemExit(127) fail-closed if binary cannot be resolved or found.
    """
    script_path = Path(__file__).resolve().parents[2] / "codex" / "bin" / "which-codex.sh"
    if script_path.exists() and os.access(script_path, os.X_OK):
        try:
            res = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                bin_path = res.stdout.strip()
                if bin_path:
                    return bin_path
        except Exception:
            pass

    codex_bin_env = os.environ.get("CODEX_BIN")
    if codex_bin_env and os.access(codex_bin_env, os.X_OK):
        return codex_bin_env

    which_path = shutil.which("codex")
    if which_path:
        return which_path

    raise SystemExit(127)


def _uses_omniroute(codex_bin: str) -> bool:
    if os.environ.get("CODEX_USE_OMNIROUTE", "1") == "0":
        return False
    if "codex-omniroute" in codex_bin:
        return True
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    key_file = codex_home / ".omniroute_key"
    config_file = codex_home / "config.toml"
    if not key_file.is_file() or not config_file.is_file():
        return False
    try:
        text = config_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'model_provider = "omniroute"' in text


class CodexAdapter(RuntimeAdapter):
    """RuntimeAdapter implementation for OpenAI Codex CLI."""

    def build_command(self, ctx: SessionContext) -> list[str]:
        codex_bin = _resolve_codex_binary()

        project_root = ctx.extras.get("project_root") or os.getcwd()

        cmd = [
            codex_bin,
            "exec",
            "--json",
            "--cd",
            str(project_root),
            "--ephemeral",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "--enable",
            _CODEX_NATIVE_COLLAB_FEATURE,
        ]
        if _uses_omniroute(codex_bin):
            cmd.extend(["-c", 'model_provider="omniroute"'])
        if ctx.model:
            cmd.extend(["--model", ctx.model])

        return cmd

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        exit_code = ctx.extras.get("exit_code")

        if (
            COLLABORATION_WAIT_TIMEOUT_REASON in raw_log
            or "SESSION_COLLAB_WAIT_TIMEOUT" in raw_log
        ):
            return SessionAnalysis(
                reason=COLLABORATION_WAIT_TIMEOUT_REASON,
                retry=True,
            )

        unsupported_tool = _detect_codex_unsupported_tool(raw_log)
        if unsupported_tool:
            return SessionAnalysis(
                reason=f"unsupported_tool_call: {unsupported_tool}",
                retry=True,
            )

        if exit_code == 127:
            return SessionAnalysis(reason="command not found", retry=False)

        if exit_code == 124:
            return SessionAnalysis(reason="codex session timeout", retry=True)

        if exit_code in (0, None):
            return SessionAnalysis(reason=None, retry=False)

        if _detect_codex_runtime_abort(raw_log):
            return SessionAnalysis(reason="aborted", retry=True)

        if detect_shell_command_not_found(raw_log):
            return SessionAnalysis(reason="command not found", retry=False)

        auth_keywords = [
            "authentication failed",
            "auth error",
            "unauthorized",
            "invalid api key",
            "401 unauthorized",
            "not logged in",
            "run codex auth",
            "auth_failed",
        ]
        error_text = _codex_error_text(raw_log).lower()
        if any(kw in error_text for kw in auth_keywords):
            return SessionAnalysis(reason="auth_failed", retry=False)

        transient_status = _CODEX_TRANSIENT_STATUS_RE.search(error_text)
        if transient_status:
            return SessionAnalysis(
                reason=f"codex_transient_api_error: {transient_status.group(0)[:180]}",
                retry=True,
            )

        if exit_code is not None and exit_code != 0:
            return SessionAnalysis(reason=f"exit_{exit_code}", retry=False)

        return SessionAnalysis(reason=None, retry=False)

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {
            "native_collaboration": True,
            "collaboration_protocol": "spawn_agent/wait",
            "collaboration_adapter": "codex_collaboration",
            "collaboration_namespace": "multi_agent_v1",
        }

    def normalize_collaboration_item(self, item: dict[str, Any]) -> dict[str, Any]:
        from loop.runtime_adapters.codex_collaboration import normalize_collaboration_item

        return normalize_collaboration_item(item)

    def subagent_lifecycle(self, cwd: Any, session_id: str) -> Any:
        from loop.runtime_adapters.subagent_lifecycle import SubagentLifecycle

        return SubagentLifecycle(cwd, session_id, "codex")

    def collaboration_block(self, ctx: SessionContext) -> str:
        from loop.runtime_adapters.collaboration import codex_collaboration_block
        return codex_collaboration_block(ctx)

    def parse_session_events(self, raw_log: str, ctx: SessionContext) -> Any:
        from loop.runtime.session_events import parse_session_events
        return parse_session_events(raw_log, ctx.runtime_id)

    def post_session(self, cwd: Any, log_path: Any, ctx: SessionContext) -> list[dict[str, Any]]:
        """Gap-fill only — live stream-filter SubagentLifecycle is SoT (Claude: no-op)."""
        if not log_path or not Path(log_path).is_file():
            return []
        from loop.codex_collab_verdict import mirror_codex_collab_verdicts_from_log
        return mirror_codex_collab_verdicts_from_log(
            cwd,
            log_path,
            session_id=str(ctx.extras.get("session_id") or ""),
        )

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
        return normalize_read_payload(payload, provider="codex", default_cwd=cwd)

    def normalize_write_event(self, payload: dict[str, Any], cwd: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import normalize_write_payload
        return normalize_write_payload(payload, provider="codex", default_cwd=cwd)

    def evaluate_context_read(self, payload: dict[str, Any], cwd: Any = None, runtime_dir: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import evaluate_read_payload
        return evaluate_read_payload(payload, provider="codex", cwd=cwd, runtime_dir=runtime_dir)

    def evaluate_context_write(self, payload: dict[str, Any], cwd: Any = None, runtime_dir: Any = None) -> Any:
        from harness.hooks.context_ledger_adapters import evaluate_write_payload
        return evaluate_write_payload(payload, provider="codex", cwd=cwd, runtime_dir=runtime_dir)
