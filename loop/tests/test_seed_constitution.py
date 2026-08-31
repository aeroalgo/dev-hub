"""Tests for loop/constitution_seed.py and epic_resolve CLI integration."""

from __future__ import annotations

import sys
import subprocess
import pytest
from pathlib import Path
from loop.constitution_seed import seed_constitution


def test_creates_constitution(tmp_path: Path):
    res = seed_constitution(cwd=tmp_path)
    assert res["ok"] is True
    target = tmp_path / "memory-bank" / "constitution.md"
    assert target.is_file()
    content = target.read_text(encoding="utf-8")
    assert "## MUST" in content


def test_creates_memory_bank_if_absent(tmp_path: Path):
    mb = tmp_path / "memory-bank"
    assert not mb.exists()
    res = seed_constitution(cwd=tmp_path)
    assert res["ok"] is True
    assert mb.is_dir()
    assert (mb / "constitution.md").is_file()


def test_placeholders_filled(tmp_path: Path):
    res = seed_constitution(cwd=tmp_path, product_name="TestProduct")
    assert res["ok"] is True
    target = tmp_path / "memory-bank" / "constitution.md"
    content = target.read_text(encoding="utf-8")
    assert "[Product name]" not in content
    assert "[constitution version]" not in content
    assert "[YYYY-MM-DD]" not in content
    assert "TestProduct Workflow Constitution" in content
    for i in range(1, 10):
        assert f"MUST-{i}" in content


def test_product_name_from_arg(tmp_path: Path):
    res = seed_constitution(cwd=tmp_path, product_name="MyApp")
    assert res["ok"] is True
    content = (tmp_path / "memory-bank" / "constitution.md").read_text(encoding="utf-8")
    assert "MyApp Workflow Constitution" in content


def test_product_name_from_dirname(tmp_path: Path):
    res = seed_constitution(cwd=tmp_path)
    assert res["ok"] is True
    content = (tmp_path / "memory-bank" / "constitution.md").read_text(encoding="utf-8")
    assert f"{tmp_path.name} Workflow Constitution" in content


def test_version_and_date_filled(tmp_path: Path):
    res = seed_constitution(cwd=tmp_path)
    assert res["ok"] is True
    content = (tmp_path / "memory-bank" / "constitution.md").read_text(encoding="utf-8")
    assert "1.0" in content
    assert "[version]" not in content
    assert "[YYYY-MM-DD]" not in content


def test_missing_template_exit2(tmp_path: Path):
    fake_hub = tmp_path / "fake_hub"
    fake_hub.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        seed_constitution(cwd=tmp_path, hub_root=fake_hub)
    assert exc_info.value.code == 2


def test_idempotency_guard(tmp_path: Path):
    seed_constitution(cwd=tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        seed_constitution(cwd=tmp_path, force=False)
    assert exc_info.value.code == 2


def test_force_overwrite(tmp_path: Path):
    seed_constitution(cwd=tmp_path)
    target = tmp_path / "memory-bank" / "constitution.md"
    target.write_text("custom content", encoding="utf-8")
    res = seed_constitution(cwd=tmp_path, force=True)
    assert res["ok"] is True
    assert "## MUST" in target.read_text(encoding="utf-8")


def test_hub_root_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DEV_HUB_CONSTITUTION_SEED", raising=False)
    hub_root = tmp_path / "hub"
    hub_root.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        seed_constitution(cwd=hub_root, hub_root=hub_root)
    assert exc_info.value.code == 2


def test_hub_root_env_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEV_HUB_CONSTITUTION_SEED", "1")
    hub_root = tmp_path / "hub"
    hub_root.mkdir()
    templates_dir = hub_root / ".cursor" / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "constitution.md").write_text("template content", encoding="utf-8")
    res = seed_constitution(cwd=hub_root, hub_root=hub_root)
    assert res["ok"] is True


def test_cli_help_exit0():
    cmd = [sys.executable, ".claude/hooks/epic_resolve.py", "seed-constitution", "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "seed-constitution" in proc.stdout or "usage:" in proc.stdout.lower()
