from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import signal
import sys
from pathlib import Path
import pytest

from harness.hooks._lib import RuntimeConfig
from loop.runner import RunnerConfig
from loop.runner.ownership import RunnerLease, RunnerLockContendedError


ROOT = Path(__file__).resolve().parents[2]


def _load_lib():
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("project_lib_runner_ownership", ROOT / ".claude/hooks/_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _owner(lib):
    return lib.RunnerOwner(
        pid=1234,
        host="runner-host",
        started_at="2026-08-05T12:00:00Z",
        session_id="session-1",
        selected_identity="BACK IMPLEMENT",
        mode="implement",
        model="claude-sonnet",
        timeout_config={"session_timeout_sec": 3600, "kill_grace_sec": 30},
    )


def test_runner_owner_is_atomic_and_cleanup_is_owner_bound(tmp_path: Path) -> None:
    lib = _load_lib()
    state_dir = tmp_path / "runtime"
    state_dir.mkdir()
    owner_path = state_dir / "runner.json"
    owner = _owner(lib)

    lib.write_runner_owner(owner_path, owner)

    assert json.loads(owner_path.read_text(encoding="utf-8")) == {
        "pid": 1234,
        "host": "runner-host",
        "started_at": "2026-08-05T12:00:00Z",
        "session_id": "session-1",
        "selected_identity": "BACK IMPLEMENT",
        "mode": "implement",
        "model": "claude-sonnet",
        "timeout_config": {"session_timeout_sec": 3600, "kill_grace_sec": 30},
        "epic_id": "",
        "phase": "",
        "step": "",
    }
    assert not (state_dir / "runner.json.tmp").exists()
    assert lib.remove_runner_owner_if_owned(owner_path, 9999, "other") is False
    assert owner_path.exists()
    assert lib.remove_runner_owner_if_owned(owner_path, 1234, "session-1") is True
    assert not owner_path.exists()


def test_runner_status_reports_owner_and_lock_without_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setattr(lib, "runner_pid_alive", lambda _pid: False)
    state_dir = tmp_path / "runtime"
    state_dir.mkdir()
    (state_dir / "runner.lock").write_text("", encoding="utf-8")
    lib.write_runner_owner(state_dir / "runner.json", _owner(lib))

    status = lib.runner_owner_status(state_dir)

    assert status["runner_active"] is False
    assert status["owner_alive"] is False
    assert status["lock_age_sec"] >= 0
    assert status["owner"]["session_id"] == "session-1"
    assert status["owner"]["timeout_config"]["session_timeout_sec"] == 3600
    assert "secret" not in json.dumps(status).lower()


def test_runner_status_reports_missing_and_malformed_owner_as_inactive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setattr(lib, "runner_pid_alive", lambda _pid: False)
    state_dir = tmp_path / "runtime"
    state_dir.mkdir()
    owner_path = state_dir / "runner.json"

    assert lib.runner_owner_status(state_dir)["owner"] is None

    owner_path.write_text("{malformed", encoding="utf-8")

    status = lib.runner_owner_status(state_dir)

    assert status["runner_active"] is False
    assert status["owner_alive"] is False
    assert status["owner"] is None
    assert "malformed" not in json.dumps(status).lower()


def test_runner_owner_replacement_does_not_remove_new_owner(tmp_path: Path) -> None:
    lib = _load_lib()
    state_dir = tmp_path / "runtime"
    state_dir.mkdir()
    owner_path = state_dir / "runner.json"

    lib.write_runner_owner(owner_path, _owner(lib))
    replacement = lib.RunnerOwner(
        pid=5678,
        host="runner-host-2",
        started_at="2026-08-05T12:01:00Z",
        session_id="session-2",
        selected_identity="BACK IMPLEMENT",
        mode="implement",
        model="claude-haiku",
        timeout_config={"session_timeout_sec": 120, "kill_grace_sec": 10},
    )
    lib.write_runner_owner(owner_path, replacement)

    assert lib.remove_runner_owner_if_owned(owner_path, 1234, "session-1") is False
    assert lib.load_runner_owner(owner_path) == replacement


def test_runner_owner_status_projects_effective_config_without_secrets(tmp_path: Path) -> None:
    lib = _load_lib()
    state_dir = tmp_path / "runtime"
    state_dir.mkdir()
    lib.write_runner_owner(state_dir / "runner.json", _owner(lib))

    status = lib.runner_owner_status(state_dir)

    assert status["owner"]["mode"] == "implement"
    assert status["owner"]["timeout_config"] == {
        "session_timeout_sec": 3600,
        "kill_grace_sec": 30,
    }
    assert "model" in status["owner"]
    assert "secret" not in json.dumps(status).lower()
    assert set(status) == {"runner_active", "owner_alive", "lock_age_sec", "owner"}


class TestRunnerLease:
    def test_acquire_and_release(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "runtime"
        lease = RunnerLease(
            state_dir=state_dir,
            session_id="test-session-123",
            mode="implement",
            model="claude-3-5-sonnet",
            install_signal_handlers=False,
        )

        assert not lease.is_acquired
        with lease:
            assert lease.is_acquired
            owner_path = state_dir / "runner.json"
            assert owner_path.is_file()
            data = json.loads(owner_path.read_text(encoding="utf-8"))
            assert data["session_id"] == "test-session-123"
            assert data["mode"] == "implement"
            assert data["selected_identity"] == "BACK IMPLEMENT"
            assert (state_dir / "runner.lock").is_file()

        assert not lease.is_acquired
        assert not (state_dir / "runner.json").exists()

    def test_lock_contention_raises_runner_lock_contended_error(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "runtime"
        state_dir.mkdir(parents=True, exist_ok=True)
        lock_file = state_dir / "runner.lock"

        # Hold flock in current process
        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o666)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        try:
            lease = RunnerLease(
                state_dir=state_dir,
                session_id="test-session-contended",
                install_signal_handlers=False,
            )
            with pytest.raises(RunnerLockContendedError) as exc_info:
                lease.acquire()

            assert exc_info.value.exit_code == 1
            assert "already active" in str(exc_info.value)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_from_config(self, tmp_path: Path) -> None:
        rc = RuntimeConfig(
            session_timeout_sec=300,
            session_kill_grace_sec=10,
            transient_retry_max=3,
            subagent_retry_max=2,
            degraded_max=2,
            status_heartbeat_sec=30,
            stream_idle_timeout_sec=60,
            collaboration_wait_timeout_sec=120,
            permission_mode="bypass",
            sources={},
            epic_runtime="claude",
        )
        config = RunnerConfig(
            hub_root=tmp_path / "hub",
            project_root=tmp_path / "project",
            state_dir=tmp_path / "runtime" / "epic",
            runtime=rc,
            permission_mode="bypass",
            headless=True,
            interactive=False,
            verbose=False,
            cli_model="claude-3-7-sonnet",
            epic_spec="T-HUB-086",
            epic_id="T-HUB-086",
            mode="implement",
        )

        lease = RunnerLease.from_config(config, install_signal_handlers=False)
        assert lease.state_dir == tmp_path / "runtime" / "epic"
        assert lease.model == "claude-3-7-sonnet"
        assert lease.mode == "implement"
        assert lease.selected_identity == "BACK IMPLEMENT"
        assert lease.timeout_config["session_timeout_sec"] == 300
        assert lease.timeout_config["kill_grace_sec"] == 10
        assert lease.timeout_config["collaboration_wait_timeout_sec"] == 120

    def test_signal_handlers_registered_and_restored(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "runtime"
        original_sigint = signal.getsignal(signal.SIGINT)

        lease = RunnerLease(
            state_dir=state_dir,
            session_id="test-sig",
            install_signal_handlers=True,
        )
        with lease:
            current_sigint = signal.getsignal(signal.SIGINT)
            assert current_sigint != original_sigint

        restored_sigint = signal.getsignal(signal.SIGINT)
        assert restored_sigint == original_sigint
