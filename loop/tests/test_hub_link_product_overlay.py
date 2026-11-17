from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

HUB_ROOT = Path(__file__).resolve().parents[2]
HUB_LINK = HUB_ROOT / "bin" / "hub-link"


def _run_hub_link(product: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DEV_HUB"] = str(HUB_ROOT)
    return subprocess.run(
        [str(HUB_LINK), "--mode", "alongside", *extra, str(product)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture()
def product_tree(tmp_path: Path) -> Path:
    root = tmp_path / "demo-app"
    root.mkdir()
    (root / "memory-bank").mkdir()
    (root / "AGENTS.md").write_text("# demo product agents\nkeep-me\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# demo claude\n@AGENTS.md\n", encoding="utf-8")
    (root / "Makefile").write_text("hello:\n\techo ok\n", encoding="utf-8")
    return root


def test_alongside_asides_product_agents_and_wires_overlays(product_tree: Path) -> None:
    result = _run_hub_link(product_tree)
    assert result.returncode == 0, result.stderr + result.stdout

    agents = product_tree / "AGENTS.md"
    claude = product_tree / "CLAUDE.md"
    assert agents.is_symlink()
    assert claude.is_symlink()
    assert agents.resolve() == (HUB_ROOT / "AGENTS.md").resolve()
    assert claude.resolve() == (HUB_ROOT / "CLAUDE.md").resolve()

    product_agents = product_tree / "AGENTS.demo-app.md"
    product_claude = product_tree / "CLAUDE.demo-app.md"
    assert product_agents.is_file()
    assert "keep-me" in product_agents.read_text(encoding="utf-8")
    assert product_claude.is_file()
    assert "@AGENTS.md" in product_claude.read_text(encoding="utf-8")

    override = product_tree / "AGENTS.override.md"
    rule = product_tree / ".cursor" / "rules.d" / "demo-app.mdc"
    assert override.is_file()
    assert "AGENTS.demo-app.md" in override.read_text(encoding="utf-8")
    assert rule.is_file()
    assert "alwaysApply: true" in rule.read_text(encoding="utf-8")
    assert "AGENTS.demo-app.md" in rule.read_text(encoding="utf-8")

    assert (product_tree / "Makefile").read_text(encoding="utf-8") == "hello:\n\techo ok\n"


def test_alongside_keeps_existing_overlays(product_tree: Path) -> None:
    (product_tree / "AGENTS.demo-app.md").write_text("# already aside\n", encoding="utf-8")
    (product_tree / "AGENTS.override.md").write_text("# custom override\n", encoding="utf-8")
    rules_d = product_tree / ".cursor" / "rules.d"
    rules_d.mkdir(parents=True)
    (rules_d / "demo-app.mdc").write_text("# custom rule\n", encoding="utf-8")

    result = _run_hub_link(product_tree)
    assert result.returncode == 0, result.stderr + result.stdout

    assert (product_tree / "AGENTS.override.md").read_text(encoding="utf-8") == "# custom override\n"
    assert (rules_d / "demo-app.mdc").read_text(encoding="utf-8") == "# custom rule\n"
    # conflicting AGENTS.md kept under stamped aside name, original product aside untouched
    stamped = list(product_tree.glob("AGENTS.demo-app.pre-hub-*.md"))
    assert len(stamped) == 1
    assert "keep-me" in stamped[0].read_text(encoding="utf-8")
    assert (product_tree / "AGENTS.demo-app.md").read_text(encoding="utf-8") == "# already aside\n"
