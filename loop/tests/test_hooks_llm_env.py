import sys
from pathlib import Path

hooks_dir = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(hooks_dir) not in sys.path:
    sys.path.insert(0, str(hooks_dir))

import _lib

def test_load_hooks_llm_env_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECT_HOOKS_LLM_FALLBACK", raising=False)
    monkeypatch.delenv("PROJECT_HOOKS_LLM_VERDICT", raising=False)
    info = _lib.load_hooks_llm_env(project_dir=tmp_path)
    assert info is not None

def test_load_hooks_llm_env_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_VERDICT", "1")
    assert _lib.hooks_llm_flag("verdict", project_dir=tmp_path) is True

def test_hooks_llm_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_HOOKS_LLM_FALLBACK", "1")
    monkeypatch.setenv("PROJECT_HOOKS_LLM_ABORT", "0")
    assert _lib.hooks_llm_flag("abort", project_dir=tmp_path) is False

def test_load_hooks_llm_env_no_file(tmp_path):
    info = _lib.load_hooks_llm_env(project_dir=tmp_path / "nonexistent")
    assert isinstance(info, dict)
