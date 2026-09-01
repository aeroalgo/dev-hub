import sys
from pathlib import Path

hooks_dir = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))

from _lib import extract_json_fence, parse_gate_verdict_message, utc_now

def test_extract_json_fence_valid():
    text = """Some text before
```json
{
  "verdict": "PASS",
  "step_id": "s11",
  "epic_id": "T-HUB-023"
}
```
Some text after"""
    res = extract_json_fence(text)
    assert isinstance(res, dict)
    assert res.get("verdict") == "PASS"

def test_extract_json_fence_no_block():
    text = "Just plain text without json fence."
    assert extract_json_fence(text) is None

def test_parse_gate_verdict_message_valid(tmp_path):
    text = """
```json
{
  "verdict": "PASS",
  "step_id": "s11",
  "epic_id": "T-HUB-023"
}
```
"""
    rec = parse_gate_verdict_message(text, str(tmp_path), "verify", recorded_at=utc_now())
    assert rec is not None
    assert rec.verdict == "PASS"
    assert rec.step_id == "s11"
    assert rec.epic_id == "T-HUB-023"

def test_parse_gate_verdict_message_invalid_payload(tmp_path):
    text = """
```json
{
  "verdict": "PASS",
  "extra_invalid_field": true
}
```
"""
    rec = parse_gate_verdict_message(text, str(tmp_path), "verify", recorded_at=utc_now())
    assert rec is None

def test_parse_gate_verdict_message_no_fence_returns_none(tmp_path):
    text = "VERDICT: PASS"
    rec = parse_gate_verdict_message(text, str(tmp_path), "verify", recorded_at=utc_now())
    assert rec is None
