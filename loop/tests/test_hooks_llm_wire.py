import sys
from pathlib import Path

hooks_dir = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))

from _lib import parse_gate_verdict_message, utc_now
from loop.gate_verdict_store import read_gate_verdict

def test_subagent_stop_calls_parse_gate_verdict(tmp_path):
    text = """Report from verify agent:
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

def test_subagent_stop_valid_json_sidecar_written(tmp_path):
    text = """
```json
{
  "verdict": "FAIL",
  "step_id": "s11",
  "epic_id": "T-HUB-023"
}
```
"""
    parse_gate_verdict_message(text, str(tmp_path), "verify", recorded_at=utc_now())
    rec = read_gate_verdict(tmp_path, "verify")
    assert rec is not None
    assert rec.verdict == "FAIL"
    assert rec.step_id == "s11"
