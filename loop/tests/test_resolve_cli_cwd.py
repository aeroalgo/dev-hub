"""Anti-mix: epic CLI cwd must not write product memory-bank into the hub."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

from _lib import hub_root, resolve_cli_cwd  # noqa: E402


def test_resolve_cli_cwd_redirects_hub_to_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = hub_root().resolve()
    prod = tmp_path / "product"
    prod.mkdir()
    monkeypatch.setenv("PROJECT_ROOT", str(prod))

    assert resolve_cli_cwd(None) == prod.resolve()
    assert resolve_cli_cwd(str(hub)) == prod.resolve()
    assert resolve_cli_cwd(".") == (
        prod.resolve() if Path.cwd().resolve() == hub else Path(".").resolve()
    )


def test_resolve_cli_cwd_keeps_explicit_non_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path / "product"))
    (tmp_path / "product").mkdir()

    assert resolve_cli_cwd(str(other)) == other.resolve()


def test_resolve_cli_cwd_without_project_root_uses_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    hub = hub_root().resolve()
    assert resolve_cli_cwd(str(hub)) == hub
