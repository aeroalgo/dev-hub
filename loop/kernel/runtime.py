from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

from .model import RuntimeResult


class Runtime:
    name = "runtime"

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        raise NotImplementedError

    def executable(self) -> str | None:
        raise NotImplementedError

    def run(self, prompt: str, *, model: str, project: Path, log_path: Path, timeout: int) -> RuntimeResult:
        binary = self.executable()
        if not binary:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(f"runtime binary unavailable: {self.name}\n", encoding="utf-8")
            return RuntimeResult(self.name, 127, log_path)
        command = self.command(prompt, model=model, project=project)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"SESSION_START runtime={self.name}\n")
            log.flush()
            proc = subprocess.Popen(
                command,
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            try:
                output, _ = proc.communicate(timeout=max(1, timeout))
            except KeyboardInterrupt:
                os.killpg(proc.pid, signal.SIGTERM)
                output, _ = proc.communicate()
                if output:
                    log.write(output)
                log.write("SESSION_INTERRUPT\n")
                return RuntimeResult(self.name, 130, log_path, interrupted=True)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    output, _ = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    output, _ = proc.communicate()
                if output:
                    log.write(output)
                log.write("SESSION_TIMEOUT\n")
                return RuntimeResult(self.name, 124, log_path, timed_out=True)
            if output:
                log.write(output)
            code = int(proc.returncode or 0)
            log.write(f"SESSION_END exit_code={code}\n")
        return RuntimeResult(self.name, code, log_path)


class ClaudeRuntime(Runtime):
    name = "claude"

    def executable(self) -> str | None:
        return os.environ.get("CLAUDE_PATH") or shutil.which("claude")

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        binary = self.executable() or "claude"
        command = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose", "--add-dir", str(project)]
        if model:
            command.extend(["--model", model])
        return command


class CodexRuntime(Runtime):
    name = "codex"

    def executable(self) -> str | None:
        return os.environ.get("CODEX_BIN") or shutil.which("codex")

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        binary = self.executable() or "codex"
        command = [binary, "exec", "--json", "--cd", str(project), prompt]
        if model:
            command.extend(["--model", model])
        return command


def runtime_for(name: str) -> Runtime:
    value = str(name or "claude").lower()
    if value == "claude":
        return ClaudeRuntime()
    if value == "codex":
        return CodexRuntime()
    raise ValueError(f"unsupported runtime: {name!r}")
