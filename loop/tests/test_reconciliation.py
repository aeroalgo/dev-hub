from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import read_event_log_result  # noqa: E402


def _load_epic_lib():
    path = ROOT / ".claude" / "hooks" / "epic_lib.py"
    spec = importlib.util.spec_from_file_location("epic_lib_reconciliation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> Path:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_restored_artifact_is_discovered_without_mtime_ordering(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    first = _write(tmp_path, "memory-bank/back/audit/demo/audit-first.yaml", "verdict: pass\n")
    second = _write(tmp_path, "memory-bank/back/audit/demo/audit-second.yaml", "verdict: fail\n")
    os.utime(first, ns=(2, 2))
    os.utime(second, ns=(1, 1))

    events = lib.reconcile_epic_events(tmp_path, "back", "demo")

    assert [event["artifact"] for event in events] == [
        "memory-bank/back/audit/demo/audit-first.yaml",
        "memory-bank/back/audit/demo/audit-second.yaml",
    ]
    assert [event["seq"] for event in events] == [1, 2]
