import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from harness.hooks.session_resilience import detect_shell_command_not_found
from loop.runtime_adapters.base import RuntimeAdapter, SessionAnalysis, SessionContext

_CODEX_ABORT_RE = re.compile(
    r"(?i)(?:session aborted(?:\s+by\b|\s*$)|codex session aborted)"
)


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
        ]
        if _uses_omniroute(codex_bin):
            cmd.extend(["-c", 'model_provider="omniroute"'])
        if ctx.model:
            cmd.extend(["--model", ctx.model])

        return cmd

    def analyze_log(self, raw_log: str, ctx: SessionContext) -> SessionAnalysis:
        exit_code = ctx.extras.get("exit_code")
        log_lower = raw_log.lower()

        if exit_code == 127:
            return SessionAnalysis(reason="command not found", retry=False)

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
        if any(kw in log_lower for kw in auth_keywords):
            return SessionAnalysis(reason="auth_failed", retry=False)

        if exit_code is not None and exit_code != 0:
            return SessionAnalysis(reason=f"exit_{exit_code}", retry=False)

        return SessionAnalysis(reason=None, retry=False)

    def prepare_extras(self, ctx: SessionContext) -> dict[str, Any]:
        return {}
