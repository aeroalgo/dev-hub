from __future__ import annotations

import codecs
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..config import LoopSettings
from .model import RuntimeResult


def _message_value(value: object) -> str | None:
    if isinstance(value, dict):
        if "message" in value:
            return _message_value(value["message"])
        if "error" in value:
            return _message_value(value["error"])
        return str(value)
    if isinstance(value, str):
        try:
            return _message_value(json.loads(value))
        except json.JSONDecodeError:
            return value
    return str(value) if value is not None else None


def _error_message(output: str) -> str | None:
    for line in reversed(output.splitlines()):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("type") not in {"error", "turn.failed"}:
            continue
        message = _message_value(payload.get("message") or payload.get("error"))
        if message:
            return message
    return None


class Runtime:
    name = "runtime"

    def __init__(self, settings: LoopSettings | None = None) -> None:
        self.settings = settings

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        raise NotImplementedError

    def executable(self) -> str | None:
        raise NotImplementedError

    def unavailable_message(self) -> str:
        return f"runtime binary unavailable: {self.name}"

    def run(self, prompt: str, *, model: str, project: Path, log_path: Path, timeout: int) -> RuntimeResult:
        binary = self.executable()
        if not binary:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            message = self.unavailable_message()
            log_path.write_text(f"RUNTIME_ERROR {message}\n", encoding="utf-8")
            return RuntimeResult(self.name, 127, log_path, message=message)
        command = self.command(prompt, model=model, project=project)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"SESSION_START runtime={self.name} model={model}\n")
            log.flush()
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=project,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                    start_new_session=True,
                )
            except OSError as exc:
                message = f"could not start {self.name}: {exc}"
                log.write(f"RUNTIME_ERROR {message}\n")
                return RuntimeResult(self.name, 127, log_path, message=message)

            output_chunks: list[str] = []
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            def emit(data: bytes = b"", *, final: bool = False) -> None:
                text = decoder.decode(data, final=final)
                if not text:
                    return
                output_chunks.append(text)
                log.write(text)
                log.flush()
                sys.stdout.write(text)
                sys.stdout.flush()

            def terminate(sig: signal.Signals) -> None:
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass

            def stop_and_collect() -> None:
                try:
                    remaining, _ = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    terminate(signal.SIGKILL)
                    remaining, _ = proc.communicate()
                if remaining:
                    emit(remaining)
                emit(final=True)

            selector = selectors.DefaultSelector()
            try:
                if proc.stdout is None:
                    raise RuntimeError("runtime stdout pipe was not created")
                selector.register(proc.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + max(1, timeout)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, max(1, timeout))
                    events = selector.select(remaining)
                    if not events:
                        raise subprocess.TimeoutExpired(command, max(1, timeout))
                    for key, _ in events:
                        data = os.read(key.fd, 65536)
                        if data:
                            emit(data)
                            continue
                        selector.unregister(key.fileobj)
                        emit(final=True)
                        wait_timeout = max(0, deadline - time.monotonic())
                        code = int(proc.wait(timeout=wait_timeout) or 0)
                        break
                    else:
                        continue
                    break
            except KeyboardInterrupt:
                terminate(signal.SIGTERM)
                stop_and_collect()
                log.write("SESSION_INTERRUPT\n")
                return RuntimeResult(self.name, 130, log_path, message="user interrupt", interrupted=True)
            except subprocess.TimeoutExpired:
                terminate(signal.SIGTERM)
                stop_and_collect()
                log.write("SESSION_TIMEOUT\n")
                return RuntimeResult(self.name, 124, log_path, message="session timeout", timed_out=True)
            finally:
                selector.close()
                if proc.stdout is not None:
                    proc.stdout.close()
            log.write(f"SESSION_END exit_code={code}\n")
        output = "".join(output_chunks)
        return RuntimeResult(self.name, code, log_path, message=_error_message(output) if code else None)


class ClaudeRuntime(Runtime):
    name = "claude"

    def executable(self) -> str | None:
        return (self.settings.claude_path if self.settings else None) or os.environ.get("CLAUDE_PATH") or shutil.which("claude")

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        binary = self.executable() or "claude"
        command = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose", "--add-dir", str(project)]
        if model:
            command.extend(["--model", model])
        return command


class CodexRuntime(Runtime):
    name = "codex"

    def executable(self) -> str | None:
        explicit = (self.settings.codex_bin if self.settings else None) or os.environ.get("CODEX_BIN")
        if explicit:
            return explicit
        use_omniroute = self.settings.codex_use_omniroute if self.settings else os.environ.get("CODEX_USE_OMNIROUTE", "1") == "1"
        if use_omniroute:
            wrapper = (self.settings.codex_omniroute_wrapper if self.settings else None) or os.environ.get("CODEX_OMNIROUTE_WRAPPER")
            if wrapper:
                return wrapper
            hub_root = os.environ.get("DEV_HUB")
            if hub_root:
                candidate = Path(hub_root) / "codex" / "bin" / "codex-omniroute.sh"
            else:
                candidate = Path(__file__).resolve().parents[2] / "codex" / "bin" / "codex-omniroute.sh"
            return str(candidate) if candidate.is_file() else None
        return shutil.which("codex")

    def unavailable_message(self) -> str:
        use_omniroute = self.settings.codex_use_omniroute if self.settings else os.environ.get("CODEX_USE_OMNIROUTE", "1") == "1"
        if use_omniroute:
            return (
                "OmniRoute is enabled but codex/bin/codex-omniroute.sh is unavailable; "
                "check DEV_HUB or set CODEX_USE_OMNIROUTE=0 for native Codex"
            )
        return "runtime binary unavailable: codex"

    def command(self, prompt: str, *, model: str, project: Path) -> list[str]:
        binary = self.executable() or "codex"
        command = [binary, "exec", "--json", "--cd", str(project), prompt]
        if model:
            command.extend(["--model", model])
        return command


def runtime_for(name: str, *, settings: LoopSettings | None = None) -> Runtime:
    value = str(name or "claude").lower()
    if value == "claude":
        return ClaudeRuntime(settings)
    if value == "codex":
        return CodexRuntime(settings)
    raise ValueError(f"unsupported runtime: {name!r}")
