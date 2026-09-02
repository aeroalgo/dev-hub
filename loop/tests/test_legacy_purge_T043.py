"""Legacy purge tests for T-HUB-043 codex runtime bridge."""

from pathlib import Path
import json
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_run_codex_session_in_prod_code():
    """Verify AC- #4: run_codex_session does not exist in loop.sh or context_loop.py."""
    loop_sh = REPO_ROOT / "loop" / "loop.sh"
    context_loop_py = REPO_ROOT / "loop" / "context_loop.py"

    if loop_sh.exists():
        assert "run_codex_session" not in loop_sh.read_text()
    if context_loop_py.exists():
        assert "run_codex_session" not in context_loop_py.read_text()


def test_hooks_json_has_generated_header():
    """Verify AC- #1: .codex/hooks.meta.json embeds GENERATED header."""
    hooks_meta = REPO_ROOT / ".codex" / "hooks.meta.json"
    assert hooks_meta.exists(), ".codex/hooks.meta.json must exist"

    data = json.loads(hooks_meta.read_text(encoding="utf-8"))
    header = str(data.get("header") or "")
    assert "GENERATED" in header, ".codex/hooks.meta.json header must contain GENERATED"


def test_sunset_inventory_empty():
    """Verify Replacement cleanup: no legacy run_codex / run_codex_session surfaces in prod code."""
    loop_dir = REPO_ROOT / "loop"
    for py_file in loop_dir.glob("*.py"):
        content = py_file.read_text()
        assert "run_codex_session" not in content, f"Found run_codex_session in {py_file}"
