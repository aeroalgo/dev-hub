import sys
from pathlib import Path
import pytest

hooks_dir = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))

from llm_structured import GateVerdictOutput, make_gate_agent, run_gate_classify

def test_gate_verdict_output_model():
    out = GateVerdictOutput(verdict="PASS", step_id="s11", epic_id="T-HUB-023")
    assert out.verdict == "PASS"
    assert out.step_id == "s11"
    assert out.epic_id == "T-HUB-023"

def test_make_gate_agent_returns_agent():
    agent = make_gate_agent("verdict")
    assert agent is not None

def test_run_gate_classify_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "0")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "0")
    res = run_gate_classify("verdict", "Some prompt text")
    assert res is None
