"""Resolve the DSH task-board Host base URL for hub-board clients."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_HOST_URL = "http://127.0.0.1:3080"


def default_dsh_home() -> Path:
    value = os.getenv("DSH_HOME")
    return Path(value).expanduser() if value else Path.home() / ".dsh"


def default_host_url(*, dsh_home: Path | None = None) -> str:
    for key in ("DSH_TASK_BOARD_HOST_URL", "DSH_WEB_URL"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value.rstrip("/")
    home = dsh_home if dsh_home is not None else default_dsh_home()
    stamp = home / "web-host-url"
    if stamp.is_file():
        text = stamp.read_text(encoding="utf-8").strip()
        if text:
            return text.rstrip("/")
    return _DEFAULT_HOST_URL
