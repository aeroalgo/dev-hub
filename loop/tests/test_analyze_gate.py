"""Tests for pre-IMPLEMENT ANALYZE gate helper."""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = str(ROOT / "loop")


def _load_gate():
    if LOOP not in sys.path:
        sys.path.insert(0, LOOP)
    import analyze_gate

    return importlib.reload(analyze_gate)


def _write(cwd: Path, rel: str, body: str) -> None:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_analyze_stale_when_index_newer(tmp_path: Path) -> None:
    gate = _load_gate()
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  status: pending\n",
    )
    idx = tmp_path / "memory-bank/back/plan/decompose-T-Y/index.yaml"
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml",
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
    )
    analyze = tmp_path / "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml"
    past = time.time() - 60
    analyze.touch()
    import os

    os.utime(analyze, (past, past))
    idx.touch()
    out = gate.analyze_required_before_implement(
        tmp_path,
        "back",
        "T-Y",
        [{"status": "pending"}],
        index_path=idx,
    )
    assert out["required"] is True
    assert out["reason"] == "analyze_stale"
