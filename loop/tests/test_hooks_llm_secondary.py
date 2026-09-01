import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

hooks_dir = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))

from _lib import extract_verdict
from llm_structured import run_gate_verdict_llm, run_abort_llm, GateVerdictOutput

def test_run_gate_verdict_llm_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "0")
    res = run_gate_verdict_llm("text", cwd=tmp_path)
    assert res is None

def test_run_gate_verdict_llm_mocked_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    
    mock_output = GateVerdictOutput(verdict="PASS", step_id="s11", epic_id="T-HUB-023")
    
    with patch("llm_structured.run_gate_classify", return_value=mock_output):
        rec = run_gate_verdict_llm("some raw text", cwd=tmp_path, agent_id="verify")
        assert rec is not None
        assert rec.verdict == "PASS"

def test_run_abort_llm_fail_soft(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "0")
    assert run_abort_llm("error", exit_code=1, cwd=tmp_path) is None

def test_sc004_valid_json_skips_pydantic_ai(tmp_path):
    text = """Here is the gate report:
```json
{
  "verdict": "PASS",
  "step_id": "s11",
  "epic_id": "T-HUB-023"
}
```
"""
    with patch("pydantic_ai.Agent.run_sync") as mock_run_sync, \
         patch("pydantic_ai.Agent.run") as mock_run, \
         patch("llm_structured.run_gate_verdict_llm") as mock_sec_llm:
        
        verdict = extract_verdict(text, cwd=str(tmp_path), agent_id="verify")
        assert verdict == "PASS"
        mock_run_sync.assert_not_called()
        mock_run.assert_not_called()
        mock_sec_llm.assert_not_called()
