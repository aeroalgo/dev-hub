#!/usr/bin/env python3
"""Synchronize agent instructions into DSH prompt presets."""

from __future__ import annotations

import argparse
from pathlib import Path

AGENT_IDS = (
    "verify-implement",
    "verify-bugfix",
    "verify-qa",
    "verify-decompose",
    "explorer",
)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
PRESETS_DIR = REPO_ROOT / "dsh" / "presets"


def strip_frontmatter(text: str) -> str:
    """Return markdown body without a leading YAML frontmatter block."""
    if not text.startswith("---"):
        return text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return text

    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "---":
            return "".join(lines[index + 1 :])
    return text


def expected_presets() -> dict[Path, str]:
    """Build expected preset contents from the agent source files."""
    return {
        PRESETS_DIR / f"{agent_id}.prompt.md": strip_frontmatter(
            (AGENTS_DIR / f"{agent_id}.md").read_text(encoding="utf-8")
        )
        for agent_id in AGENT_IDS
    }


def sync(*, check: bool = False) -> int:
    """Write presets, or check that generated files are up to date."""
    presets = expected_presets()
    if check:
        return int(
            any(
                not path.is_file() or path.read_text(encoding="utf-8") != content
                for path, content in presets.items()
            )
        )

    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in presets.items():
        path.write_text(content, encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit with status 1 when generated presets are stale",
    )
    args = parser.parse_args()
    return sync(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
