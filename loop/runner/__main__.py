"""Executable entrypoint for python3 -m loop.runner."""

from __future__ import annotations

from loop.runner.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
