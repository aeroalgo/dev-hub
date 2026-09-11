"""Provider-neutral session invoker delegating to runtime adapters and session resilience."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

from harness.hooks.session_resilience import (
    SessionExecutionResult,
    execute_session,
)
from loop.runner import SessionPort, SessionRequest, SessionResult
from loop.runtime_adapters.base import (
    RuntimeAdapter,
    RuntimePreparationResult,
    SessionContext,
)
from loop.runtime_adapters.common import get_adapter_for_runtime


class SessionInvoker(SessionPort):
    """Executes a bounded session via resolved RuntimeAdapter and session_resilience."""

    def __init__(
        self,
        adapter_factory: Callable[[str], RuntimeAdapter] | None = None,
    ) -> None:
        self.adapter_factory = adapter_factory or get_adapter_for_runtime

    def invoke(self, request: SessionRequest) -> SessionResult:
        """Invoke a session according to SessionRequest specification."""
        # 1. Resolve runtime adapter
        try:
            adapter = self.adapter_factory(request.runtime_id)
        except Exception as exc:
            # Unknown runtime / adapter resolution failure -> fail-closed with clear diagnostic and zero fallback
            diag_msg = "==> HALT: unknown or invalid runtime '" + str(request.runtime_id) + "': " + str(exc) + chr(10)
            sys.stderr.write(diag_msg)
            sys.stderr.flush()
            request.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(request.log_file, "a", encoding="utf-8") as f:
                f.write(diag_msg)
            return SessionResult(
                exit_code=2,
                runtime_id=request.runtime_id,
                log_file=request.log_file,
                interrupted=False,
            )

        # 2. Check runtime preparation (binary existence, profile installation, etc.)
        if hasattr(adapter, "prepare_runtime"):
            try:
                prep: RuntimePreparationResult = adapter.prepare_runtime(
                    hub_root=request.hub_root,
                    project_root=request.project_root,
                    extras=dict(request.runtime_extras),
                )
            except Exception as exc:
                prep = RuntimePreparationResult(
                    ok=False,
                    exit_code=127,
                    error="runtime preparation error: " + str(exc),
                )
            if not prep.ok:
                err_msg = "==> HALT: " + str(prep.error or "runtime preparation failed") + chr(10)
                sys.stderr.write(err_msg)
                sys.stderr.flush()
                request.log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(request.log_file, "a", encoding="utf-8") as f:
                    f.write(err_msg)
                return SessionResult(
                    exit_code=prep.exit_code or 127,
                    runtime_id=request.runtime_id,
                    log_file=request.log_file,
                    interrupted=False,
                )

        # 3. Read prompt
        try:
            prompt_text = request.prompt_file.read_text(encoding="utf-8")
        except Exception as exc:
            err_msg = "==> ERROR: cannot read prompt file '" + str(request.prompt_file) + "': " + str(exc) + chr(10)
            sys.stderr.write(err_msg)
            sys.stderr.flush()
            request.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(request.log_file, "a", encoding="utf-8") as f:
                f.write(err_msg)
            return SessionResult(
                exit_code=1,
                runtime_id=request.runtime_id,
                log_file=request.log_file,
                interrupted=False,
            )

        # 4. Prepare context & build command
        extras: dict[str, Any] = dict(request.runtime_extras)
        extras.setdefault("hub_root", request.hub_root)
        extras.setdefault("project_root", request.project_root)
        extras.setdefault("permission_mode", request.permission_mode)
        extras.setdefault("mode", request.mode)
        extras.setdefault("extra_args", request.extra_args)

        if hasattr(adapter, "prepare_extras"):
            try:
                adapter_extras = adapter.prepare_extras(
                    SessionContext(
                        prompt=prompt_text,
                        phase=request.phase,
                        model=request.model,
                        runtime_id=request.runtime_id,
                        session_id=request.session_id,
                        extras=extras,
                    )
                )
                if adapter_extras:
                    extras.update(adapter_extras)
            except Exception:
                pass

        ctx = SessionContext(
            prompt=prompt_text,
            phase=request.phase,
            model=request.model,
            runtime_id=request.runtime_id,
            session_id=request.session_id,
            extras=extras,
        )

        try:
            command = adapter.build_command(ctx)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 127
            err_msg = "==> HALT: adapter command generation exited (" + str(code) + ") for '" + str(request.runtime_id) + "'" + chr(10)
            sys.stderr.write(err_msg)
            sys.stderr.flush()
            request.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(request.log_file, "a", encoding="utf-8") as f:
                f.write(err_msg)
            return SessionResult(
                exit_code=code,
                runtime_id=request.runtime_id,
                log_file=request.log_file,
                interrupted=False,
            )
        except Exception as exc:
            err_msg = "==> HALT: adapter command generation failed for '" + str(request.runtime_id) + "': " + str(exc) + chr(10)
            sys.stderr.write(err_msg)
            sys.stderr.flush()
            request.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(request.log_file, "a", encoding="utf-8") as f:
                f.write(err_msg)
            return SessionResult(
                exit_code=127,
                runtime_id=request.runtime_id,
                log_file=request.log_file,
                interrupted=False,
            )

        # 5. Resolve working directory, stdin, progress mode, stream filter
        if hasattr(adapter, "resolve_working_directory"):
            cwd = adapter.resolve_working_directory(
                project_root=request.project_root,
                hub_root=request.hub_root,
                ctx=ctx,
            )
        else:
            cwd = request.project_root

        requires_stdin = False
        if hasattr(adapter, "requires_stdin_prompt"):
            requires_stdin = adapter.requires_stdin_prompt(mode=request.mode)
        stdin_text = prompt_text if requires_stdin else None

        if hasattr(adapter, "progress_mode"):
            progress_mode = adapter.progress_mode()
        else:
            progress_mode = "tool_json"

        stream_filter_cmd = None
        if request.mode == "headless" and hasattr(adapter, "resolve_stream_filter"):
            stream_filter_cmd = adapter.resolve_stream_filter(request.hub_root)

        collab_wait_timeout = None
        if "collaboration_wait_timeout" in extras:
            collab_wait_timeout = float(extras["collaboration_wait_timeout"])
        elif "EPIC_COLLAB_WAIT_TIMEOUT_SEC" in os.environ:
            try:
                collab_wait_timeout = float(os.environ["EPIC_COLLAB_WAIT_TIMEOUT_SEC"])
            except ValueError:
                pass

        # 6. Execute session via session_resilience
        exec_res: SessionExecutionResult = execute_session(
            command=command,
            mode=request.mode,
            session_id=request.session_id,
            timeout=float(request.timeout_sec),
            kill_grace=float(request.kill_grace_sec),
            log_path=request.log_file,
            expected_model=request.model,
            heartbeat_sec=float(request.heartbeat_sec) if request.heartbeat_sec else None,
            idle_timeout=float(request.idle_timeout_sec) if request.idle_timeout_sec else None,
            collaboration_wait_timeout=collab_wait_timeout,
            stdin_text=stdin_text,
            progress_mode=progress_mode,
            cwd=cwd,
            stream_filter_cmd=stream_filter_cmd,
        )

        return SessionResult(
            exit_code=exec_res.exit_code,
            runtime_id=request.runtime_id,
            log_file=exec_res.log_file,
            interrupted=exec_res.interrupted,
        )


__all__ = [
    "SessionInvoker",
]
