from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


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
    }
    assert not (state_dir / "runner.json.tmp").exists()
    assert lib.remove_runner_owner_if_owned(owner_path, 9999, "other") is False
    assert owner_path.exists()
    assert lib.remove_runner_owner_if_owned(owner_path, 1234, "session-1") is True
    assert not owner_path.exists()


def test_runner_status_reports_owner_and_lock_without_secrets(tmp_path: Path) -> None:
    lib = _load_lib()
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


def test_runner_status_reports_missing_and_malformed_owner_as_inactive(tmp_path: Path) -> None:
    lib = _load_lib()
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

