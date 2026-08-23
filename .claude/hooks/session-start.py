#!/usr/bin/env python3
"""SessionStart — inject epic initialUserMessage (fresh -p session)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import emit, product_cwd, read_stdin  # noqa: E402
from epic_lib import session_start_payload  # noqa: E402


def main() -> None:
    data = read_stdin()
    cwd = str(product_cwd(data.get("cwd") or ""))
    source = data.get("source") or data.get("session_source") or ""
    payload = session_start_payload(cwd, source)
    if not payload:
        return
    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            **payload,
        }
    }
    emit(out)


if __name__ == "__main__":
    main()
