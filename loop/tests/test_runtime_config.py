from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_lib():
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("project_lib_runtime_config", ROOT / ".claude/hooks/_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_config_uses_bounded_defaults_and_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.delenv("EPIC_SESSION_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("EPIC_SESSION_KILL_GRACE_SEC", raising=False)
    monkeypatch.delenv("EPIC_TRANSIENT_RETRY_MAX", raising=False)
    monkeypatch.delenv("EPIC_DEGRADED_MAX", raising=False)
    monkeypatch.delenv("EPIC_STATUS_HEARTBEAT_SEC", raising=False)
    monkeypatch.delenv("EPIC_STREAM_IDLE_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("EPIC_PERMISSION_MODE", raising=False)
    monkeypatch.delenv("EPIC_RUNTIME", raising=False)

    config = lib.resolve_runtime_config(tmp_path)

    assert config.session_timeout_sec > 0
    assert config.session_kill_grace_sec > 0
    assert config.transient_retry_max >= 0
    assert config.degraded_max > 0
    assert config.status_heartbeat_sec == 30
    assert config.stream_idle_timeout_sec == 300
    assert set(config.sources) == {
        "EPIC_SESSION_TIMEOUT_SEC",
        "EPIC_SESSION_KILL_GRACE_SEC",
        "EPIC_TRANSIENT_RETRY_MAX",
        "EPIC_DEGRADED_MAX",
        "EPIC_STATUS_HEARTBEAT_SEC",
        "EPIC_STREAM_IDLE_TIMEOUT_SEC",
        "EPIC_PERMISSION_MODE",
        "EPIC_RUNTIME",
    }
    assert set(config.sources.values()) <= {"project", "default"}
    assert config.sources["EPIC_RUNTIME"] == "default"


def test_runtime_config_prefers_process_values_and_reports_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/project.env").write_text("EPIC_SESSION_TIMEOUT_SEC=120\n", encoding="utf-8")
    monkeypatch.setenv("EPIC_SESSION_TIMEOUT_SEC", "300")

    config = lib.resolve_runtime_config(tmp_path)

    assert config.session_timeout_sec == 300
    assert config.sources["EPIC_SESSION_TIMEOUT_SEC"] == "process"


@pytest.mark.parametrize("value", ["", "abc", "0", "-1", "999999"])
def test_runtime_config_rejects_invalid_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_SESSION_TIMEOUT_SEC", value)

    with pytest.raises(lib.RuntimeConfigError) as exc_info:
        lib.resolve_runtime_config(tmp_path)

    assert exc_info.value.diagnostics[0]["code"] == "invalid_runtime_config"
    assert exc_info.value.diagnostics[0]["key"] == "EPIC_SESSION_TIMEOUT_SEC"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("EPIC_SESSION_KILL_GRACE_SEC", "0"),
        ("EPIC_SESSION_KILL_GRACE_SEC", "999999"),
        ("EPIC_TRANSIENT_RETRY_MAX", "-1"),
        ("EPIC_TRANSIENT_RETRY_MAX", "101"),
        ("EPIC_DEGRADED_MAX", "0"),
        ("EPIC_DEGRADED_MAX", "101"),
        ("EPIC_STATUS_HEARTBEAT_SEC", "abc"),
        ("EPIC_STATUS_HEARTBEAT_SEC", "0"),
        ("EPIC_STATUS_HEARTBEAT_SEC", "3601"),
        ("EPIC_STREAM_IDLE_TIMEOUT_SEC", "abc"),
        ("EPIC_STREAM_IDLE_TIMEOUT_SEC", "29"),
        ("EPIC_STREAM_IDLE_TIMEOUT_SEC", "86401"),
    ],
)
def test_runtime_config_rejects_invalid_bounded_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
) -> None:
    lib = _load_lib()
    monkeypatch.setenv(key, value)

    with pytest.raises(lib.RuntimeConfigError) as exc_info:
        lib.resolve_runtime_config(tmp_path)

    assert exc_info.value.diagnostics[0]["code"] == "invalid_runtime_config"
    assert exc_info.value.diagnostics[0]["key"] == key


def test_runtime_config_accepts_bounds_and_empty_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_SESSION_TIMEOUT_SEC", "60")
    monkeypatch.setenv("EPIC_SESSION_KILL_GRACE_SEC", "1")
    monkeypatch.setenv("EPIC_TRANSIENT_RETRY_MAX", "0")
    monkeypatch.setenv("EPIC_DEGRADED_MAX", "100")
    monkeypatch.setenv("EPIC_STATUS_HEARTBEAT_SEC", "")
    monkeypatch.setenv("EPIC_STREAM_IDLE_TIMEOUT_SEC", "")
    monkeypatch.setenv("EPIC_RUNTIME", "claude")

    config = lib.resolve_runtime_config(tmp_path)

    assert config.session_timeout_sec == 60
    assert config.session_kill_grace_sec == 1
    assert config.transient_retry_max == 0
    assert config.degraded_max == 100
    assert config.status_heartbeat_sec is None
    assert config.stream_idle_timeout_sec is None
    assert set(config.sources.values()) <= {"process", "project"}
    assert config.sources["EPIC_SESSION_TIMEOUT_SEC"] == "process"
    assert config.sources["EPIC_SESSION_KILL_GRACE_SEC"] == "process"
    assert config.sources["EPIC_TRANSIENT_RETRY_MAX"] == "process"
    assert config.sources["EPIC_DEGRADED_MAX"] == "process"
    assert config.sources["EPIC_STATUS_HEARTBEAT_SEC"] == "process"
    assert config.sources["EPIC_STREAM_IDLE_TIMEOUT_SEC"] == "process"


def test_runtime_config_status_is_secret_free(tmp_path: Path) -> None:
    lib = _load_lib()

    status = lib.runtime_config_status(lib.resolve_runtime_config(tmp_path))

    assert "EPIC_SESSION_TIMEOUT_SEC" in status["effective"]
    assert "EPIC_STREAM_IDLE_TIMEOUT_SEC" in status["effective"]
    assert "secret" not in str(status).lower()
    assert "sources" in status


def test_runtime_config_resolves_permission_mode_from_project_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _load_lib()
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/project.env").write_text(
        "EPIC_PERMISSION_MODE=bypassPermissions\n", encoding="utf-8"
    )
    monkeypatch.delenv("EPIC_PERMISSION_MODE", raising=False)

    config = lib.resolve_runtime_config(tmp_path)
    status = lib.runtime_config_status(config)

    assert status["effective"]["EPIC_PERMISSION_MODE"] == "bypassPermissions"
    assert status["sources"]["EPIC_PERMISSION_MODE"] == "project"
    assert "project.env" not in str(status)


def test_runtime_config_permission_mode_process_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _load_lib()
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/project.env").write_text(
        "EPIC_PERMISSION_MODE=bypassPermissions\n", encoding="utf-8"
    )
    monkeypatch.setenv("EPIC_PERMISSION_MODE", "dontAsk")

    config = lib.resolve_runtime_config(tmp_path)
    status = lib.runtime_config_status(config)

    assert status["effective"]["EPIC_PERMISSION_MODE"] == "dontAsk"
    assert status["sources"]["EPIC_PERMISSION_MODE"] == "process"


def test_runtime_config_rejects_invalid_permission_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_PERMISSION_MODE", "invalid")

    with pytest.raises(lib.RuntimeConfigError) as exc_info:
        lib.resolve_runtime_config(tmp_path)

    assert exc_info.value.diagnostics[0]["key"] == "EPIC_PERMISSION_MODE"
    assert exc_info.value.diagnostics[0]["code"] == "invalid_runtime_config"
    assert exc_info.value.diagnostics[0]["reason"] == "unsupported_permission_mode"


def test_epic_runtime_defaults_to_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.delenv("EPIC_RUNTIME", raising=False)

    config = lib.resolve_runtime_config(tmp_path)

    assert config.epic_runtime == "claude"


def test_epic_runtime_dsh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    config = lib.resolve_runtime_config(tmp_path)

    assert config.epic_runtime == "dsh"


def test_epic_runtime_invalid_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_RUNTIME", "foo")

    with pytest.raises(lib.RuntimeConfigError) as exc_info:
        lib.resolve_runtime_config(tmp_path)

    assert exc_info.value.diagnostics[0] == {
        "code": "invalid_runtime_config",
        "key": "EPIC_RUNTIME",
        "reason": "unsupported_runtime",
    }


def test_epic_runtime_status_included(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    monkeypatch.setenv("EPIC_RUNTIME", "dsh")

    config = lib.resolve_runtime_config(tmp_path)
    status = lib.runtime_config_status(config)

    assert status["effective"]["EPIC_RUNTIME"] == "dsh"
    assert status["sources"]["EPIC_RUNTIME"] == "process"


def test_epic_runtime_project_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib = _load_lib()
    env_dir = tmp_path / ".claude"
    env_dir.mkdir()
    (env_dir / "project.env").write_text("EPIC_RUNTIME=dsh\n", encoding="utf-8")
    monkeypatch.delenv("EPIC_RUNTIME", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    config = lib.resolve_runtime_config(tmp_path)

    assert config.epic_runtime == "dsh"
    assert config.sources["EPIC_RUNTIME"] == "project"
