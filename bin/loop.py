#!/usr/bin/env python3
"""Canonical Python entrypoint for the single-cursor loop."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


HUB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUB_ROOT))
os.environ.setdefault("HUB_ROOT", str(HUB_ROOT))
os.environ.setdefault("DEV_HUB", str(HUB_ROOT))


def _argv() -> list[str]:
    values = list(sys.argv[1:])
    if values and values[0] in {"claude", "codex"}:
        os.environ.setdefault("EPIC_RUNTIME", values.pop(0))
    if values:
        candidate = Path(values[0]).expanduser()
        if candidate.is_dir() and (candidate / "memory-bank").is_dir():
            project = str(candidate.resolve())
            values.pop(0)
            if "--project" not in values and "--cwd" not in values:
                values = [*values, "--project", project]
    return values


def main() -> int:
    from loop.kernel.cli import main as cli_main
    from loop.config import activate_loop_process

    try:
        activate_loop_process()
        return int(cli_main(_argv()))
    except KeyboardInterrupt:
        print("loop interrupted by user", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"loop fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("  entrypoint: bin/loop.py", file=sys.stderr)
        print("  hint: set LOOP_DEBUG=1 for traceback", file=sys.stderr)
        if os.environ.get("LOOP_DEBUG") == "1":
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
