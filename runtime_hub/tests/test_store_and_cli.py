from pathlib import Path

import pytest

from runtime_hub.cli import main
from runtime_hub.errors import (
    ActiveConflict,
    InvalidProfileConfig,
    UnknownProfile,
)
from runtime_hub.models import Profile
from runtime_hub.store import ProfileStore


def write_profiles(root: Path, *records: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = ["profiles:"]
    for record in records:
        lines.append(f"  - id: {record['id']}")
        lines.append(f"    runtime: {record['runtime']}")
        lines.append(f"    home: {record['home']}")
    (root / "profiles.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_profile_schema_and_store_roundtrip(tmp_path: Path) -> None:
    profile = Profile.from_mapping(
        {
            "id": "gpt-work",
            "runtime": "codex",
            "home": "gpt-work",
            "model": "gpt-5",
            "env": {"PROFILE": "work"},
            "notes": "work account",
        }
    )
    assert profile.runtime == "codex"
    write_profiles(tmp_path, {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"})
    store = ProfileStore(tmp_path)

    selected = store.use("gpt-work")

    assert selected.id == "gpt-work"
    assert store.read_active() == "gpt-work"
    assert (tmp_path / "profiles" / "gpt-work").is_dir()


def test_list_use_status_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    write_profiles(tmp_path, {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"})
    monkeypatch.setenv("RUNTIME_HUB_HOME", str(tmp_path))

    assert main(["list"]) == 0
    assert "gpt-work" in capsys.readouterr().out
    assert main(["use", "gpt-work"]) == 0
    assert "gpt-work" in capsys.readouterr().out
    assert main(["status"]) == 0
    output = capsys.readouterr().out
    assert "gpt-work" in output
    assert "codex" in output


def test_use_unknown_profile_does_not_mutate_active(tmp_path: Path) -> None:
    write_profiles(tmp_path, {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"})
    store = ProfileStore(tmp_path)
    store.use("gpt-work")

    with pytest.raises(UnknownProfile):
        store.use("missing")

    assert store.read_active() == "gpt-work"


def test_use_conflict_requires_force(tmp_path: Path) -> None:
    write_profiles(
        tmp_path,
        {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"},
        {"id": "claude-work", "runtime": "claude", "home": "claude-work"},
    )
    store = ProfileStore(tmp_path)
    store.use("gpt-work")

    with pytest.raises(ActiveConflict):
        store.use("claude-work")

    assert store.read_active() == "gpt-work"
    assert store.use("claude-work", force=True).id == "claude-work"


def test_require_force_and_dirty_state_fail_closed_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_profiles(
        tmp_path,
        {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"},
        {"id": "claude-work", "runtime": "claude", "home": "claude-work"},
    )
    store = ProfileStore(tmp_path)
    store.use("gpt-work")
    monkeypatch.setenv("HUB_RUNTIME_REQUIRE_FORCE", "1")

    with pytest.raises(ActiveConflict):
        store.use("claude-work")
    assert store.read_active() == "gpt-work"

    monkeypatch.delenv("HUB_RUNTIME_REQUIRE_FORCE")
    store.dirty_file.touch()
    with pytest.raises(ActiveConflict):
        store.use("claude-work")
    assert store.read_active() == "gpt-work"


def test_invalid_profile_config_fails_closed(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "profiles.yaml").write_text("profiles:\n  - id: broken\n", encoding="utf-8")

    with pytest.raises(InvalidProfileConfig):
        ProfileStore(tmp_path).list_profiles()


def test_no_profile_home_fallback(tmp_path: Path) -> None:
    write_profiles(tmp_path, {"id": "gpt-work", "runtime": "codex", "home": "gpt-work"})
    store = ProfileStore(tmp_path)

    home = store.resolve_home(store.list_profiles()[0])

    assert home == (tmp_path / "profiles" / "gpt-work").resolve()
    assert home != Path.home() / ".codex"
