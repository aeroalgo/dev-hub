from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
RESILIENCE = HOOKS / "session_resilience.py"


def _load_resilience():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("session_resilience_last_path", RESILIENCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_resilience_last_path"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clear_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PROJECT_ROOT", "HUB_ROOT", "DEV_HUB"):
        monkeypatch.delenv(key, raising=False)


def test_last_session_path_hub_root_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC+ 4: HUB_ROOT + slug → hub/runtime/<slug>/epic/last-session.json."""
    hub = tmp_path / "fakehub"
    hub.mkdir()
    monkeypatch.setenv("HUB_ROOT", str(hub))
    cwd = tmp_path / "my-epic"
    cwd.mkdir()

    sr = _load_resilience()
    got = sr.last_session_path(cwd, track="epic")

    expected = hub.resolve() / "runtime" / "my-epic" / "epic" / "last-session.json"
    assert got == expected


def test_last_session_path_dev_hub_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC+ 4 variant: DEV_HUB env → same hub routing."""
    hub = tmp_path / "devhub"
    hub.mkdir()
    monkeypatch.setenv("DEV_HUB", str(hub))
    cwd = tmp_path / "my-epic"
    cwd.mkdir()

    sr = _load_resilience()
    got = sr.last_session_path(cwd)

    expected = hub.resolve() / "runtime" / "my-epic" / "epic" / "last-session.json"
    assert got == expected


def test_last_session_path_no_hub_product_layout(tmp_path: Path) -> None:
    """Without hub env → product .claude/runtime/epic/last-session.json."""
    sr = _load_resilience()
    got = sr.last_session_path(tmp_path, track="epic")
    assert got == tmp_path.resolve() / ".claude" / "runtime" / "epic" / "last-session.json"


def test_last_session_path_does_not_delete_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC− 2: builds path only — existing sibling dirs stay."""
    hub = tmp_path / "fakehub"
    keep = hub / "runtime" / "my-epic" / "epic" / "keep-me"
    keep.mkdir(parents=True)
    marker = keep / "marker.txt"
    marker.write_text("stay", encoding="utf-8")
    monkeypatch.setenv("HUB_ROOT", str(hub))
    cwd = tmp_path / "my-epic"
    cwd.mkdir()

    sr = _load_resilience()
    sr.last_session_path(cwd)

    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "stay"


def test_last_session_path_importable_without_env() -> None:
    """Import last_session_path works without hub/project env."""
    sr = _load_resilience()
    assert callable(sr.last_session_path)
