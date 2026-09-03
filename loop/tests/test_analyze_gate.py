"""Tests for pre-IMPLEMENT ANALYZE gate helper."""
from __future__ import annotations

import importlib.util
import os
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


def _write(cwd: Path, rel: str, body: str) -> Path:
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_analyze_mtime_drift_passes_when_complete_and_aligned(tmp_path: Path) -> None:
    gate = _load_gate()
    idx = _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  status: pending\n",
    )
    analyze = _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n"
        "coverage:\n  - requirement_id: FR-1\n    step_ids: [s01]\n    status: covered\n",
    )
    past = time.time() - 60
    os.utime(analyze, (past, past))
    idx.touch()
    out = gate.analyze_required_before_implement(
        tmp_path,
        "back",
        "T-Y",
        [{"id": "s01", "status": "pending"}],
        index_path=idx,
    )
    assert out["required"] is False
    assert out["reason"] == "analyze_pass"


def test_analyze_stale_when_index_fingerprint_mismatch(tmp_path: Path) -> None:
    gate = _load_gate()
    idx = _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nindex_fingerprint: sha256:deadbeef\n"
        "metrics:\n  critical_count: 0\n",
    )
    out = gate.analyze_required_before_implement(
        tmp_path,
        "back",
        "T-Y",
        [{"id": "s01", "status": "pending"}],
        index_path=idx,
    )
    assert out["required"] is True
    assert out["reason"] == "analyze_stale"


def test_analyze_stale_when_step_refs_missing_from_index(tmp_path: Path) -> None:
    gate = _load_gate()
    idx = _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\nmetrics:\n  critical_count: 0\n"
        "findings:\n  - id: A1\n    severity: LOW\n    step_ref: s99\n",
    )
    out = gate.analyze_required_before_implement(
        tmp_path,
        "back",
        "T-Y",
        [{"id": "s01", "status": "pending"}],
        index_path=idx,
    )
    assert out["required"] is True
    assert out["reason"] == "analyze_stale"


def test_analyze_pass_when_fingerprint_checked_via_index_md(tmp_path: Path) -> None:
    """index.md path must fingerprint index.yaml SoT — not md bytes."""
    gate = _load_gate()
    yaml_body = (
        "schema: epic-decompose-index/v1\nplan_id: T-Y\nsteps:\n"
        "- id: s01\n  status: pending\n"
    )
    idx_yaml = _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.yaml",
        yaml_body,
    )
    idx_md = _write(
        tmp_path,
        "memory-bank/back/plan/decompose-T-Y/index.md",
        "| step_id | status |\n| s01 | pending |\n",
    )
    fp = gate.index_content_fingerprint(idx_yaml)
    _write(
        tmp_path,
        "memory-bank/back/analyze/T-Y/analyze-20260830-pass.yaml",
        "schema: epic-analyze/v1\nstatus: complete\n"
        f"index_fingerprint: {fp}\n"
        "metrics:\n  critical_count: 0\n",
    )
    out = gate.analyze_required_before_implement(
        tmp_path,
        "back",
        "T-Y",
        [{"id": "s01", "status": "pending"}],
        index_path=idx_md,
    )
    assert out["required"] is False, out
    assert out["reason"] == "analyze_pass"
