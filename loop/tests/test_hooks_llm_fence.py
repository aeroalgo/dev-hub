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


def test_extract_json_fence_info_string_schema_id():
    """Models often emit ```json loop-gate-verdict/v1 — must still parse."""
    text = """```json loop-gate-verdict/v1
{
  "schema": "loop-gate-verdict/v1",
  "agent_id": "verify-implement",
  "verdict": "PASS",
  "step_id": "s01",
  "epic_id": "T-HUB-047-harness-mb-scaffold-epic-layout",
  "recorded_at": "2026-09-03T00:00:00Z"
}
```"""
    res = extract_json_fence(text)
    assert isinstance(res, dict)
    assert res.get("verdict") == "PASS"
    assert res.get("schema") == "loop-gate-verdict/v1"


def test_extract_json_fence_no_block():
    text = "Just plain text without json fence."
    assert extract_json_fence(text) is None

def test_parse_gate_verdict_message_valid(tmp_path):
    text = """
```json
{
  "verdict": "PASS",
  "step_id": "s11",
  "session_id": "test-sess",
  "epic_id": "T-HUB-023"
}
```
"""
    rec = parse_gate_verdict_message(
        text,
        str(tmp_path),
        "verify",
        recorded_at=utc_now(),
        session_id="test-sess",
    )
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
    rec = parse_gate_verdict_message(
        text,
        str(tmp_path),
        "verify",
        recorded_at=utc_now(),
        session_id="test-sess",
    )
    assert rec is None

def test_parse_gate_verdict_message_canonical_loop_gate_verdict(tmp_path):
    text = """
```json
{
  "schema": "loop-gate-verdict/v1",
  "agent_id": "verify-implement",
  "verdict": "PASS",
  "step_id": "s03",
  "session_id": "test-sess",
  "epic_id": "T-HUB-055",
  "recorded_at": "2026-09-03T00:00:00Z"
}
```
"""
    rec = parse_gate_verdict_message(
        text,
        str(tmp_path),
        "verify-implement",
        recorded_at=utc_now(),
        session_id="test-sess",
    )
    assert rec is not None
    assert rec.verdict == "PASS"
    assert rec.step_id == "s03"
    assert rec.epic_id == "T-HUB-055"


def test_parse_gate_verdict_message_no_fence_returns_none(tmp_path):
    text = "VERDICT: PASS"
    rec = parse_gate_verdict_message(text, str(tmp_path), "verify", recorded_at=utc_now())
    assert rec is None


def test_agent_pretool_denies_repair_without_fail(tmp_path):
    """TM-006: repair without prior FAIL is denied with semantic_repair_without_fail code."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    agent_pretool = root / ".claude" / "hooks" / "agent-pretool.py"
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    (agents / "gate-repair.md").write_text("---\nname: gate-repair\noverlay:\n  managed: true\n---\n", encoding="utf-8")
    env_path = tmp_path / ".claude" / "project.env"
    env_path.write_text("PROJECT_WORKFLOW_HOOKS=loop\nPROJECT_AGENT_GATE_REPAIR_MODEL=sonnet\n", encoding="utf-8")

    payload = {
        "tool_name": "Agent",
        "session_id": "test-repair-without-fail",
        "cwd": str(tmp_path),
        "tool_input": {
            "subagent_type": "gate-repair",
            "prompt": "BLOCKERS: fix x\nALLOW WRITE:\n1. foo.py\nVERIFY:\n- pytest\n",
        },
    }
    env = os.environ.copy()
    env["EPIC_LOOP"] = "1"
    proc = subprocess.run(
        [sys.executable, str(agent_pretool)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    reason = out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
    assert "semantic_repair_without_fail" in reason
