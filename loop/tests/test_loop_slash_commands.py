from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

_SLASH = (
    ".claude/commands/loop-run.md",
    ".claude/commands/epic-run.md",
    ".claude/commands/program-run.md",
    ".claude/commands/epic-status.md",
)

_FENCE = re.compile(r"```(?:bash)?\n(.*?)```", re.DOTALL)
_BAD_CLI = re.compile(
    r"(?:"
    r"--track\b"
    r"|--id\b"
    r"|--gap\b"
    r"|--resume-implement\b"
    r"|/(?:epic|program)-loop\.sh"
    r")"
)


def test_loop_slash_command_examples_use_current_cli() -> None:
    for rel in _SLASH:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "./loop/loop.sh" in text
        for block in _FENCE.findall(text):
            hit = _BAD_CLI.search(block)
            assert hit is None, f"{rel} example still uses removed CLI: {hit.group(0)!r}"


def test_legacy_loop_wrapper_scripts_removed() -> None:
    assert not (ROOT / "loop" / "epic-loop.sh").exists()
    assert not (ROOT / "loop" / "program-loop.sh").exists()
    assert (ROOT / "loop" / "loop.sh").is_file()


def test_readme_lists_loop_run_without_track() -> None:
    readme = (ROOT / ".claude" / "README.md").read_text(encoding="utf-8")
    assert "/loop-run" in readme
    assert "--track program" not in readme
    assert "--track epic" not in readme
