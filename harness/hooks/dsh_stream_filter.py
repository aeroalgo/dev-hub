#!/usr/bin/env python3
"""Hide dsh-claude-compat startup noise while preserving session output."""
from __future__ import annotations

import sys


_NOISE_PREFIXES = (
    "⭐ dsh-claude-compat works for you?",
    "Show some love: https://github.com/biedongbin/dsh-claude-compat",
    "dsh-claude-compat: SessionStart hook output:",
)


def is_noise(line: str) -> bool:
    return line.lstrip().startswith(_NOISE_PREFIXES)


def main() -> None:
    for line in sys.stdin:
        if not is_noise(line):
            sys.stdout.write(line)
            sys.stdout.flush()


if __name__ == "__main__":
    main()
