"""Signal-safe checkout locking and atomic runner ownership lifecycle."""

from __future__ import annotations

import fcntl
import os
import signal
import socket
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from harness.hooks._lib import (
    RunnerOwner,
    load_runner_owner,
    remove_runner_owner_if_owned,
    runner_owner_status,
    write_runner_owner,
)
from loop.runner import RunnerConfig


class RunnerLockContendedError(RuntimeError):
    """Raised when another loop runner holds runner.lock."""

    def __init__(
        self,
        message: str = "==> ERROR: another loop runner is already active",
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class RunnerLease:
    """POSIX flock + atomic runner.json ownership context manager with signal-safe cleanup."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        session_id: str | None = None,
        pid: int | None = None,
        host: str | None = None,
        started_at: str | None = None,
        selected_identity: str = "",
        mode: str = "",
        model: str = "",
        timeout_config: Mapping[str, int | None] | None = None,
        epic_id: str = "",
        phase: str = "",
        step: str = "",
        lock_file_name: str = "runner.lock",
        owner_file_name: str = "runner.json",
        install_signal_handlers: bool = True,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.session_id = session_id or str(uuid.uuid4())
        self.pid = pid if pid is not None else os.getpid()
        self.host = host or socket.gethostname()
        self.started_at = (
            started_at
            or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        self.selected_identity = selected_identity
        self.mode = mode
        self.model = model
        self.timeout_config = (
            dict(timeout_config) if timeout_config is not None else {}
        )
        self.epic_id = epic_id
        self.phase = phase
        self.step = step
        self.lock_file_name = lock_file_name
        self.owner_file_name = owner_file_name
        self.install_signal_handlers = install_signal_handlers

        self.lock_path = self.state_dir / self.lock_file_name
        self.owner_path = self.state_dir / self.owner_file_name
        self._lock_fd: int | None = None
        self._previous_handlers: dict[int, Any] = {}
        self._acquired = False

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    @classmethod
    def from_config(
        cls,
        config: RunnerConfig,
        *,
        session_id: str | None = None,
        install_signal_handlers: bool = True,
    ) -> RunnerLease:
        sid = (
            session_id
            or os.environ.get("EPIC_RUNNER_SESSION_ID")
            or str(uuid.uuid4())
        )
        os.environ["EPIC_RUNNER_SESSION_ID"] = sid

        timeout_cfg: dict[str, int | None] = {}
        if config.runtime:
            timeout_cfg = {
                "session_timeout_sec": config.runtime.session_timeout_sec,
                "kill_grace_sec": config.runtime.session_kill_grace_sec,
                "collaboration_wait_timeout_sec": config.runtime.collaboration_wait_timeout_sec,
            }

        selected_id = ""
        if config.mode == "implement":
            selected_id = "BACK IMPLEMENT"

        return cls(
            state_dir=config.state_dir,
            session_id=sid,
            selected_identity=selected_id,
            mode=config.mode or "",
            model=config.cli_model or "",
            timeout_config=timeout_cfg,
            epic_id=config.epic_id or "",
            install_signal_handlers=install_signal_handlers,
        )

    def acquire(self) -> None:
        if self._acquired:
            return

        self.state_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o666)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            os.close(fd)
            raise RunnerLockContendedError(
                "==> ERROR: another loop runner is already active",
                exit_code=1,
            ) from exc

        self._lock_fd = fd

        owner = RunnerOwner(
            pid=self.pid,
            host=self.host,
            started_at=self.started_at,
            session_id=self.session_id,
            selected_identity=self.selected_identity
            or ("BACK IMPLEMENT" if self.mode == "implement" else ""),
            mode=self.mode,
            model=self.model,
            timeout_config=self.timeout_config,
            epic_id=self.epic_id,
            phase=self.phase,
            step=self.step,
        )
        write_runner_owner(self.owner_path, owner)
        self._acquired = True

        if (
            self.install_signal_handlers
            and threading.current_thread() is threading.main_thread()
        ):
            self._setup_signals()

    def release(self) -> None:
        self._restore_signals()
        self._cleanup()

    def _setup_signals(self) -> None:
        def _on_sigint(signum: int, frame: Any) -> None:
            self._cleanup()
            sys.stderr.write("==> LOOP STOPPED (Ctrl+C)\n")
            sys.stderr.flush()
            sys.exit(130)

        def _on_term(signum: int, frame: Any) -> None:
            self._cleanup()
            sys.exit(128 + signum if signum > 0 else 1)

        for sig, handler in [
            (signal.SIGINT, _on_sigint),
            (signal.SIGTERM, _on_term),
            (signal.SIGHUP, _on_term),
        ]:
            try:
                self._previous_handlers[sig] = signal.signal(sig, handler)
            except (ValueError, OSError):
                pass

    def _restore_signals(self) -> None:
        for sig, handler in self._previous_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        self._previous_handlers.clear()

    def _cleanup(self) -> None:
        if self._acquired:
            remove_runner_owner_if_owned(
                self.owner_path, self.pid, self.session_id
            )
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = None
        self._acquired = False

    def __enter__(self) -> RunnerLease:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


__all__ = [
    "RunnerLease",
    "RunnerLockContendedError",
]
