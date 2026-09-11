"""Tests for DSH adapter dispatch, binary resolution, and profile preparation without sourcing loop.sh."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest
from loop.runtime_adapters.dsh import DshAdapter
from loop.runtime_adapters.base import SessionContext


ROOT = Path(__file__).resolve().parents[2]
FAKE_DSH = ROOT / "loop" / "tests" / "fixtures" / "fake_dsh.sh"


def test_dsh_adapter_resolves_custom_dsh_bin(monkeypatch, tmp_path: Path) -> None:
    adapter = DshAdapter()
    fake_bin = tmp_path / "custom-dsh"
    fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    monkeypatch.setenv("DSH_BIN", str(fake_bin))
    cmd = adapter.resolve_binary(ROOT)
    assert cmd == [str(fake_bin)]


def test_dsh_adapter_resolves_which_dsh_resolver(monkeypatch, tmp_path: Path) -> None:
    adapter = DshAdapter()
    resolver = tmp_path / "which-dsh.sh"
    resolver.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' {shlex.quote(str(FAKE_DSH))}\n", encoding="utf-8")
    resolver.chmod(0o755)

    monkeypatch.delenv("DSH_BIN", raising=False)
    monkeypatch.setenv("DSH_RESOLVER", str(resolver))
    cmd = adapter.resolve_binary(ROOT)
    assert cmd == [str(FAKE_DSH)]


def test_dsh_adapter_build_command() -> None:
    adapter = DshAdapter()
    ctx = SessionContext(
        runtime_id="dsh",
        model="deepseek-coder",
        phase="IMPLEMENT",
        prompt="hello from context",
        extras={
            "dsh_profile": "epic-implement",
            "dsh_command": ["/path/to/dsh"],
        },
    )
    cmd = adapter.build_command(ctx)
    assert cmd == ["/path/to/dsh", "--profile", "epic-implement", "hello from context"]


def test_dsh_adapter_prepare_fails_closed_on_missing_binary(monkeypatch) -> None:
    adapter = DshAdapter()
    monkeypatch.delenv("DSH_BIN", raising=False)
    monkeypatch.setenv("DSH_RESOLVER", "/nonexistent/resolver.sh")
    monkeypatch.setenv("PATH", "")

    res = adapter.prepare_runtime(hub_root=ROOT, project_root=ROOT)
    assert not res.ok
    assert res.exit_code == 127
    assert "dsh binary not found" in res.error


def test_dsh_adapter_ensure_profiles_runs_installers(monkeypatch, tmp_path: Path) -> None:
    adapter = DshAdapter()
    installer = tmp_path / "install-profiles.sh"
    hooks_installer = tmp_path / "install-cc-hooks.sh"
    install_log = tmp_path / "install.log"
    installer.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' profiles >> {shlex.quote(str(install_log))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hooks_installer.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' hooks >> {shlex.quote(str(install_log))}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    installer.chmod(0o755)
    hooks_installer.chmod(0o755)

    monkeypatch.delenv("DSH_PROFILES_READY", raising=False)
    monkeypatch.setenv("DSH_PROFILE_INSTALLER", str(installer))
    monkeypatch.setenv("DSH_HOOKS_INSTALLER", str(hooks_installer))

    res = adapter.ensure_profiles(hub_root=ROOT, dsh_home=tmp_path / "dsh-home")
    assert res.ok
    assert (tmp_path / "install.log").read_text(encoding="utf-8").splitlines() == [
        "profiles",
        "hooks",
    ]
