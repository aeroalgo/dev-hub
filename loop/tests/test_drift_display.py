from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = str(ROOT / ".claude" / "hooks")
if HOOKS not in sys.path:
    sys.path.insert(0, HOOKS)


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write(cwd: Path, rel: str, body: str) -> None:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


VALID_AC = """---
schema: loop-handoff/v1
step_id: s01
plan_id: T-HUB-001
role: back
phase: BACK PLAN
status: in_progress
---

## load_now
1. foo
"""


def test_status_shows_drift_when_nonzero(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", VALID_AC)
    state = {
        "schema_version": "loop-state/v2",
        "active": True,
        "drift_counters": {
            "index_mirror_repair": 2,
            "handoff_projected": 0,
        },
    }
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(state),
    )

    res = ctx.status(tmp_path)
    assert "drift_counters" in res
    assert res["drift_counters"] == {"index_mirror_repair": 2}


def test_status_no_drift_when_zero(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", VALID_AC)
    state = {
        "schema_version": "loop-state/v2",
        "active": True,
        "drift_counters": {
            "index_mirror_repair": 0,
            "handoff_projected": 0,
        },
    }
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(state),
    )

    res = ctx.status(tmp_path)
    assert "drift_counters" not in res
