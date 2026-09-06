from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HOOKS = ROOT / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from _lib import extract_repair_result  # noqa: E402


def test_extract_repair_result_from_json_fence() -> None:
    text = """
REPAIR: done
```json
{
  "schema": "loop-repair-result/v1",
  "parent_evidence_id": "evidence-fail-001",
  "agent_id": "gate-repair",
  "status": "done",
  "fixed_blockers": ["diagnostic_code_mismatch"],
  "remaining_blockers": [],
  "recorded_at": "2026-09-01T12:00:00Z"
}
```
"""
    result = extract_repair_result(text)
    assert result is not None
    assert result["status"] == "done"
    assert result["parent_evidence_id"] == "evidence-fail-001"
    assert "diagnostic_code_mismatch" in result["fixed_blockers"]


def test_extract_repair_result_done_with_remaining_fails_closed() -> None:
    text = """
```json
{
  "schema": "loop-repair-result/v1",
  "parent_evidence_id": "evidence-fail-001",
  "agent_id": "gate-repair",
  "status": "done",
  "fixed_blockers": ["b1"],
  "remaining_blockers": ["b2"],
  "recorded_at": "2026-09-01T12:00:00Z"
}
```
"""
    result = extract_repair_result(text)
    assert result is None


def test_extract_repair_result_from_repair_line_deny_prose() -> None:
    result = extract_repair_result("REPAIR: fail\nno json")
    assert result is None


def test_extract_repair_result_invalid_json_schema_fails_closed() -> None:
    text = """
```json
{
  "schema": "loop-repair-result/v1",
  "status": "invalid_status"
}
```
"""
    result = extract_repair_result(text)
    assert result is None
