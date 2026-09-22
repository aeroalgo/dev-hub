from __future__ import annotations

import codecs
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ..config import LoopSettings
from .model import RuntimeResult


_TOOL_PROGRESS_RE = re.compile(r'"type"\s*:\s*"(?:tool_use|tool_result)"')
_CODEX_PROGRESS_RE = re.compile(r'"type"\s*:\s*"(?:command_execution|agent_message)"')
_COLLAB_TERMINAL_STATES = frozenset(
    {"completed", "failed", "errored", "error", "cancelled", "closed", "stopped"}
)


def _progress_seen(tail: str, chunk: str, *, mode: str) -> tuple[bool, str]:
    """Detect real provider progress while tolerating JSON split across reads."""
    if not chunk:
        return False, tail
    if mode == "stream_bytes":
        return True, tail
    combined = tail + chunk
    pattern = _CODEX_PROGRESS_RE if mode == "codex_json" else _TOOL_PROGRESS_RE
    found = any(match.end() > len(tail) for match in pattern.finditer(combined))
    return found, combined[-128:]


def _collaboration_state(
    text: str,
    pending: set[str],
    wait_started: float | None,
    *,
    now: float,
) -> tuple[set[str], float | None]:
    """Track native Codex children so a long wait is not mistaken for silence."""
    for raw_line in text.splitlines():
        try:
            payload = json.loads(raw_line)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if not isinstance(item, dict) or item.get("type") != "collab_tool_call":
            continue
        tool = str(item.get("tool") or "").rsplit(".", 1)[-1]
        if tool not in {"spawn_agent", "wait"}:
            continue
        receiver_ids = {
            str(value).strip()
            for value in (item.get("receiver_thread_ids") or [])
            if str(value).strip()
        }
        states = item.get("agents_states")
        if not isinstance(states, dict):
            states = {}
        for thread_id, state in states.items():
            thread = str(thread_id).strip()
            if not thread:
                continue
            status = str(state.get("status") or "").lower() if isinstance(state, dict) else ""
            if status in _COLLAB_TERMINAL_STATES:
                pending.discard(thread)
            else:
                pending.add(thread)
        if tool == "spawn_agent":
            pending.update(receiver_ids)
        elif payload.get("type") == "item.started" and receiver_ids:
            pending.update(receiver_ids)
        if pending and wait_started is None:
            wait_started = now
        if not pending:
            wait_started = None
    return pending, wait_started


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
    progress_mode = "stream_bytes"

    def __init__(self, settings: LoopSettings | None = None, *, progress: bool = True) -> None:
        self.settings = settings
        self.progress = progress
        self._progress_buffer = ""

    def _progress_line(self, line: str) -> str | None:
        return None

    def _progress_finished(self, code: int) -> str | None:
        return None

    def _progress_started(self, project: Path, prompt: str) -> None:
        self._progress_buffer = ""

    def _watchdog_settings(self) -> tuple[float | None, float | None, float, float | None]:
        """Return heartbeat, idle, kill-grace and child-wait limits."""
        settings = self.settings
        heartbeat = getattr(settings, "status_heartbeat", None) if settings else None
        idle = getattr(settings, "stream_idle_timeout", None) if settings else None
        kill_grace = float(getattr(settings, "session_kill_grace", 5) if settings else 5)
        collab = getattr(settings, "collaboration_wait_timeout", None) if settings else None
        return (
            float(heartbeat) if heartbeat is not None else None,
            float(idle) if idle is not None else None,
            max(0.0, kill_grace),
            float(collab) if collab is not None else None,
        )

    def _emit_progress(self, text: str, *, final: bool = False) -> None:
        self._progress_buffer += text
        lines = self._progress_buffer.split("\n")
        if final:
            self._progress_buffer = ""
        else:
            self._progress_buffer = lines.pop()
        for line in lines:
            rendered = self._progress_line(line.rstrip("\r"))
            if rendered and self.progress:
                print(rendered, flush=True)

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
        self._progress_started(project, prompt)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_sec, idle_timeout, kill_grace, collaboration_timeout = self._watchdog_settings()
        session_id = log_path.stem
        started = time.monotonic()
        last_activity = started
        last_heartbeat = started
        heartbeat_count = 0
        activity_tail = ""
        collaboration_buffer = ""
        collaboration_pending: set[str] = set()
        collaboration_wait_started: float | None = None
        last_activity_label = "starting"
        timed_out = False
        idle_timed_out = False
        collaboration_wait_timed_out = False

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

            def emit(data: bytes = b"", *, final: bool = False) -> str:
                text = decoder.decode(data, final=final)
                if text:
                    output_chunks.append(text)
                    log.write(text)
                    log.flush()
                if text or final:
                    self._emit_progress(text, final=final)
                return text

            def terminate(sig: signal.Signals) -> None:
                try:
                    os.killpg(proc.pid, sig)
                except (OSError, ProcessLookupError):
                    try:
                        proc.send_signal(sig)
                    except OSError:
                        pass

            def stop_and_collect() -> None:
                try:
                    remaining, _ = proc.communicate(timeout=kill_grace)
                except subprocess.TimeoutExpired:
                    terminate(signal.SIGKILL)
                    remaining, _ = proc.communicate()
                if remaining:
                    emit(remaining)
                emit(final=True)

            def write_heartbeat(now: float, *, state: str) -> None:
                nonlocal last_heartbeat, heartbeat_count
                if heartbeat_sec is None or now - last_heartbeat < heartbeat_sec:
                    return
                elapsed = now - started
                idle_for = now - last_activity
                heartbeat = (
                    f"SESSION_HEARTBEAT session={session_id} elapsed={elapsed:.1f}s "
                    f"idle_for={idle_for:.1f}s state={state} "
                    f"activity=\"{last_activity_label}\"\n"
                )
                log.write(heartbeat)
                log.flush()
                heartbeat_count += 1
                if self.progress:
                    print(
                        f"==> heartbeat: session={session_id} elapsed={elapsed:.1f}s "
                        f"idle_for={idle_for:.1f}s state={state} "
                        f"activity=\"{last_activity_label}\"",
                        flush=True,
                    )
                last_heartbeat = now

            selector = selectors.DefaultSelector()
            try:
                if proc.stdout is None:
                    raise RuntimeError("runtime stdout pipe was not created")
                selector.register(proc.stdout, selectors.EVENT_READ)
                deadline = started + max(1, timeout)
                while True:
                    now = time.monotonic()
                    remaining = deadline - now
                    if remaining <= 0:
                        timed_out = proc.poll() is None
                        if timed_out:
                            terminate(signal.SIGTERM)
                            stop_and_collect()
                        break
                    poll_for = min(
                        remaining,
                        0.25,
                        heartbeat_sec or remaining,
                        idle_timeout or remaining,
                        collaboration_timeout or remaining,
                    )
                    events = selector.select(max(0.01, poll_for))
                    now = time.monotonic()
                    if collaboration_pending:
                        last_activity = now
                        last_activity_label = "native collaboration wait"
                    write_heartbeat(now, state="running" if proc.poll() is None else "exited")
                    if (
                        idle_timeout is not None
                        and proc.poll() is None
                        and not collaboration_pending
                        and now - last_activity >= idle_timeout
                    ):
                        idle_timed_out = True
                        idle_for = now - last_activity
                        log.write(
                            f"SESSION_IDLE_TIMEOUT session={session_id} "
                            f"idle_timeout={idle_timeout:g}s idle_for={idle_for:.1f}s\n"
                        )
                        log.flush()
                        if self.progress:
                            print(
                                f"==> idle timeout: session={session_id} "
                                f"idle_for={idle_for:.1f}s limit={idle_timeout:g}s",
                                flush=True,
                            )
                        terminate(signal.SIGTERM)
                        stop_and_collect()
                        break
                    if (
                        collaboration_timeout is not None
                        and collaboration_pending
                        and collaboration_wait_started is not None
                        and proc.poll() is None
                        and now - collaboration_wait_started >= collaboration_timeout
                    ):
                        collaboration_wait_timed_out = True
                        waited = now - collaboration_wait_started
                        threads = ",".join(sorted(collaboration_pending))
                        log.write(
                            f"SESSION_COLLAB_WAIT_TIMEOUT session={session_id} "
                            f"timeout={collaboration_timeout:g}s wait_for={waited:.1f}s "
                            f"threads={threads}\n"
                        )
                        log.flush()
                        if self.progress:
                            print(
                                f"==> native collaboration wait timeout: session={session_id} "
                                f"wait_for={waited:.1f}s limit={collaboration_timeout:g}s "
                                f"threads={threads}",
                                flush=True,
                            )
                        terminate(signal.SIGTERM)
                        stop_and_collect()
                        break
                    for key, _ in events:
                        data = os.read(key.fd, 65536)
                        if data:
                            text = emit(data)
                            now = time.monotonic()
                            if self.progress_mode == "codex_json":
                                collaboration_buffer += text
                                complete_lines = collaboration_buffer.split("\n")
                                collaboration_buffer = complete_lines.pop()
                                collaboration_pending, collaboration_wait_started = _collaboration_state(
                                    "\n".join(complete_lines),
                                    collaboration_pending,
                                    collaboration_wait_started,
                                    now=now,
                                )
                                collaboration_buffer = collaboration_buffer[-64_000:]
                            progressed, activity_tail = _progress_seen(
                                activity_tail, text, mode=self.progress_mode
                            )
                            if progressed:
                                last_activity = now
                                last_activity_label = (
                                    "output" if self.progress_mode == "stream_bytes" else self.progress_mode
                                )
                            continue
                        selector.unregister(key.fileobj)
                        emit(final=True)
                        if proc.poll() is not None:
                            break
                    else:
                        continue
                    if proc.poll() is not None and not selector.get_map():
                        break
            except KeyboardInterrupt:
                terminate(signal.SIGTERM)
                stop_and_collect()
                log.write("SESSION_INTERRUPT\n")
                elapsed_sec = time.monotonic() - started
                log.write(f"SESSION_END exit_code=130 elapsed={elapsed_sec:.3f}s\n")
                return RuntimeResult(
                    self.name,
                    130,
                    log_path,
                    message="user interrupt",
                    interrupted=True,
                    elapsed_sec=elapsed_sec,
                    heartbeat_count=heartbeat_count,
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate(signal.SIGTERM)
                stop_and_collect()
            finally:
                selector.close()
                if proc.stdout is not None:
                    proc.stdout.close()
            if timed_out:
                log.write(f"SESSION_TIMEOUT session={session_id} timeout={timeout:g}s\n")
                code = 124
            elif idle_timed_out or collaboration_wait_timed_out:
                code = 124
            else:
                code = int(proc.returncode or 0)
            elapsed_sec = time.monotonic() - started
            log.write(f"SESSION_END session={session_id} exit_code={code} elapsed={elapsed_sec:.3f}s\n")
            log.flush()
            finished = self._progress_finished(code)
            if self.progress and finished:
                print(finished, flush=True)
        output = "".join(output_chunks)
        if timed_out:
            message = "session timeout"
        elif idle_timed_out:
            message = "stream idle timeout"
        elif collaboration_wait_timed_out:
            message = "native collaboration wait timeout"
        else:
            message = _error_message(output) if code else None
        return RuntimeResult(
            self.name,
            code,
            log_path,
            message=message,
            timed_out=timed_out,
            idle_timed_out=idle_timed_out,
            collaboration_wait_timed_out=collaboration_wait_timed_out,
            elapsed_sec=elapsed_sec,
            heartbeat_count=heartbeat_count,
        )


class ClaudeRuntime(Runtime):
    name = "claude"
    progress_mode = "tool_json"

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
    progress_mode = "codex_json"

    def __init__(self, settings: LoopSettings | None = None, *, progress: bool = True) -> None:
        super().__init__(settings, progress=progress)
        self._progress_project = Path.cwd()
        self._collab_agents: dict[str, str] = {}
        self._processed_verdicts: set[tuple[str, str]] = set()
        self._displayed_messages: set[str] = set()
        self._collab_lifecycle = None
        self._expected_subagent_type: str | None = None

    def _progress_started(self, project: Path, prompt: str) -> None:
        super()._progress_started(project, prompt)
        self._progress_project = project
        self._collab_agents: dict[str, str] = {}
        self._processed_verdicts: set[tuple[str, str]] = set()
        self._displayed_messages: set[str] = set()
        self._expected_subagent_type = None
        try:
            from .lifecycle import SubagentLifecycle
            from .store import LoopPaths
            from .engine import LoopEngine

            self._collab_lifecycle = SubagentLifecycle(LoopPaths.for_project(project))
            cursor = self._collab_lifecycle.engine.store.read()
            if cursor is not None:
                self._expected_subagent_type = LoopEngine._required_gate_agent(cursor.phase)
        except Exception:
            self._collab_lifecycle = None

    def _progress_finished(self, code: int) -> str:
        return f"  {'✓' if code == 0 else '✗'} codex session finished (exit={code})"

    @staticmethod
    def _compact(value: object, limit: int = 240) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return f"{text[: limit - 1]}…"

    @classmethod
    def _command_kind(cls, command: str) -> str:
        normalized = command.strip().lower()
        if any(token in normalized for token in ("apply_patch", " > ", " >> ", "tee ", "mkdir ", "touch ", "rm ", "mv ", "cp ")):
            return "write"
        first = normalized.split(maxsplit=1)[0] if normalized else "bash"
        if first in {"cat", "head", "tail", "sed", "awk", "rg", "grep", "find", "ls", "pwd", "readlink", "stat", "file", "du", "wc"}:
            return "read"
        return "bash"

    @classmethod
    def _item_message(cls, item: dict[str, object]) -> str | None:
        for key in ("text", "message", "summary", "content"):
            value = item.get(key)
            message = cls._display_message(value)
            if message:
                return message
        return None

    @classmethod
    def _display_message(cls, value: object, limit: int = 4000) -> str | None:
        if isinstance(value, dict):
            value = value.get("text") or value.get("message") or value.get("content")
        text = str(value or "").strip()
        if not text:
            return None
        if len(text) > limit:
            text = text[: limit - 1] + "…"
        if "```" in text:
            return text
        return cls._compact(text, limit=limit)

    @staticmethod
    def _collaboration_tool(item: dict[str, object]) -> str:
        raw = str(item.get("tool") or "").strip()
        return raw.rsplit(".", 1)[-1] or "unknown"

    def _collaboration_label(self, item: dict[str, object]) -> str:
        from .verdict import MANAGED_SUBAGENTS, normalize_agent_id

        for key in ("agent_type", "subagent_type", "agent_name", "name"):
            value = str(item.get(key) or "").strip()
            if value:
                normalized = normalize_agent_id(value)
                return normalized if normalized in MANAGED_SUBAGENTS else value
        prompt = str(item.get("prompt") or "")
        match = re.search(r"(?im)^\s*(?:agent_type|subagent_type)\s*[:=]\s*([a-z0-9_-]+)", prompt)
        if match:
            normalized = normalize_agent_id(match.group(1))
            return normalized if normalized in MANAGED_SUBAGENTS else normalized
        lowered_prompt = prompt.lower()
        if "loop-repair-result/v1" in lowered_prompt or (
            "blockers:" in lowered_prompt and "allow write:" in lowered_prompt
        ):
            return "gate-repair"
        if self._expected_subagent_type:
            return self._expected_subagent_type
        heading = re.search(r"(?im)^\s*#\s+([a-z][a-z0-9_-]{1,63})(?=\s|:|$)", prompt)
        return heading.group(1) if heading else "unknown"

    @classmethod
    def _child_message(cls, state: dict[str, object]) -> str | None:
        for key in ("message", "output", "result", "last_message"):
            message = cls._display_message(state.get(key))
            if message:
                return message
        return None

    def _child_verdict(self, thread_id: str, agent_id: str, message: str) -> str | None:
        if self._collab_lifecycle is None:
            return None
        from .verdict import MANAGED_GATE_AGENTS, MANAGED_SUBAGENTS, extract_json_fence, normalize_agent_id

        payload, _ = extract_json_fence(message)
        normalized_agent = normalize_agent_id(agent_id)
        if isinstance(payload, dict):
            resolved_agent = normalize_agent_id(str(payload.get("agent_id") or ""))
            if resolved_agent in MANAGED_SUBAGENTS:
                agent_id = resolved_agent
                normalized_agent = resolved_agent
        if (
            not isinstance(payload, dict)
            and "loop-gate-verdict/v1" not in message
            and "loop-repair-result/v1" not in message
        ):
            return None
        key = (thread_id, message)
        if key in self._processed_verdicts:
            return None
        self._processed_verdicts.add(key)
        try:
            action = self._collab_lifecycle.stop(
                {
                    "cwd": str(self._progress_project),
                    "agent_type": agent_id,
                    "last_assistant_message": message,
                }
            )
        except Exception as exc:
            return f"    verdict hook error: {exc}"
        if action.transition:
            transition = action.transition
            metadata = transition.get("metadata", {})
            if metadata.get("repair_status"):
                return (
                    f"    repair {agent_id}={metadata['repair_status']} -> "
                    f"{transition.get('phase')}/{transition.get('step_id')}; re-verify required"
                )
            verdict = metadata.get("verdict") or transition.get("event")
            suffix = "" if verdict == "PASS" or transition.get("event") == "qa_failed" else "; repair required before finish"
            return (
                f"    verdict {agent_id}={verdict} -> "
                f"{transition.get('phase')}/{transition.get('step_id')}{suffix}"
            )
        if not action.ok:
            return f"    gate {agent_id} handoff rejected: {action.reason}; respawn the same agent with exact GATE_IDENTITY"
        return f"    verdict {agent_id}: {action.reason}"

    def _collaboration_progress(self, item: dict[str, object]) -> str:
        tool = self._collaboration_tool(item)
        label = self._collaboration_label(item)
        thread_ids = [str(value) for value in item.get("receiver_thread_ids") or [] if str(value).strip()]
        if tool == "spawn_agent":
            for thread_id in thread_ids:
                self._collab_agents[thread_id] = label
            suffix = f" ids={','.join(thread_ids)}" if thread_ids else ""
            return f"  → subagent spawn type={label}{suffix}"
        if tool == "wait":
            return f"  → subagent wait children={len(thread_ids)}"
        return f"  → subagent {tool}"

    def _completed_collaboration_progress(self, item: dict[str, object]) -> str:
        tool = self._collaboration_tool(item)
        states = item.get("agents_states")
        if not isinstance(states, dict) or not states:
            return f"  ← subagent {tool} completed (child output pending)"
        lines: list[str] = []
        for raw_thread_id, raw_state in states.items():
            thread_id = str(raw_thread_id)
            if not isinstance(raw_state, dict):
                continue
            status = str(raw_state.get("status") or "unknown")
            label = self._collab_agents.get(thread_id) or self._collaboration_label(raw_state)
            message = self._child_message(raw_state)
            if label == "unknown" and message:
                from .verdict import MANAGED_SUBAGENTS, extract_json_fence, normalize_agent_id

                payload, _ = extract_json_fence(message)
                if isinstance(payload, dict):
                    resolved = normalize_agent_id(str(payload.get("agent_id") or ""))
                    if resolved in MANAGED_SUBAGENTS:
                        label = resolved
            lines.append(f"  ← subagent {label} id={thread_id} status={status}")
            if message:
                message_key = self._compact(message, limit=4000)
                if message_key not in self._displayed_messages:
                    self._displayed_messages.add(message_key)
                    lines.append("    " + message.replace("\n", "\n    "))
                verdict = self._child_verdict(thread_id, label, message)
                if verdict:
                    lines.append(verdict)
            if status.lower() in {"completed", "failed", "error", "closed"}:
                self._collab_agents.pop(thread_id, None)
        return "\n".join(lines) if lines else f"  ← subagent {tool} completed"

    def _progress_line(self, line: str) -> str | None:
        raw = line.strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            if raw.startswith("SESSION_"):
                return None
            return f"  │ {self._compact(raw)}"
        if not isinstance(payload, dict):
            return None

        event_type = str(payload.get("type") or "")
        if event_type in {"error", "turn.failed"}:
            message = _message_value(payload.get("message") or payload.get("error"))
            return f"  ! {self._compact(message)}" if message else None

        item = payload.get("item")
        if not isinstance(item, dict):
            return None
        item_type = str(item.get("type") or "")
        if item_type == "command_execution":
            command = self._compact(item.get("command") or item.get("cmd") or "command")
            kind = self._command_kind(command)
            if event_type == "item.started":
                return f"  • {kind:<5} {command}"
            if event_type == "item.completed":
                exit_code = item.get("exit_code")
                status = "✓" if exit_code in (None, 0) and str(item.get("status") or "") not in {"failed", "error"} else "✗"
                suffix = f" (exit={exit_code})" if exit_code is not None else ""
                return f"  {status} {kind:<5} finished{suffix}"
            return None
        if item_type == "collab_tool_call":
            tool = self._collaboration_tool(item)
            status = str(item.get("status") or "")
            if event_type == "item.started":
                return self._collaboration_progress(item)
            if event_type == "item.completed" or status in {"completed", "failed"}:
                if event_type == "item.completed":
                    return self._completed_collaboration_progress(item)
                marker = "✓" if status != "failed" else "✗"
                return f"  {marker} subagent {tool}"
            return f"  • subagent {tool}"
        if event_type == "item.started" and item_type == "reasoning":
            return "  … reasoning"
        if event_type == "item.completed" and item_type in {"agent_message", "reasoning"}:
            message = self._item_message(item)
            if message:
                message_key = self._compact(message, limit=4000)
                if message_key in self._displayed_messages:
                    return None
                self._displayed_messages.add(message_key)
                prefix = "  │" if item_type == "agent_message" else "  …"
                formatted_message = message.replace("\n", "\n  │ ")
                return f"{prefix} {formatted_message}"
        if event_type == "item.completed" and item_type == "error":
            message = self._item_message(item)
            return f"  ! {message}" if message else None
        return None

    def _omniroute_wrapper(self) -> str | None:
        configured = (self.settings.codex_omniroute_wrapper if self.settings else None) or os.environ.get(
            "CODEX_OMNIROUTE_WRAPPER"
        )
        if configured:
            candidate = Path(os.path.expanduser(configured))
        else:
            hub_root = os.environ.get("DEV_HUB")
            candidate = (
                Path(hub_root) / "codex" / "bin" / "codex-omniroute.sh"
                if hub_root
                else Path(__file__).resolve().parents[2] / "codex" / "bin" / "codex-omniroute.sh"
            )
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None

    def executable(self) -> str | None:
        explicit = (self.settings.codex_bin if self.settings else None) or os.environ.get("CODEX_BIN")
        if explicit:
            return explicit
        use_omniroute = self.settings.codex_use_omniroute if self.settings else os.environ.get("CODEX_USE_OMNIROUTE", "1") == "1"
        if use_omniroute:
            wrapper = self._omniroute_wrapper()
            if wrapper:
                return wrapper
            return None
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
        command = [
            binary,
            "exec",
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "--cd",
            str(project),
        ]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command


def runtime_for(name: str, *, settings: LoopSettings | None = None, progress: bool = True) -> Runtime:
    value = str(name or "claude").lower()
    if value == "claude":
        return ClaudeRuntime(settings, progress=progress)
    if value == "codex":
        return CodexRuntime(settings, progress=progress)
    raise ValueError(f"unsupported runtime: {name!r}")
