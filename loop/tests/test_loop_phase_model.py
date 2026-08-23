from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    hooks = str(ROOT / ".claude" / "hooks")
    loop = str(ROOT / "loop")
    for p in (hooks, loop):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(
        "context_loop_phase_model", ROOT / "loop" / "context_loop.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_loop_phase_key_from_armed_step() -> None:
    ctx = _load_ctx()
    assert ctx.loop_phase_key("BACK IMPLEMENT", "DECOMPOSE") == "DECOMPOSE"
    assert ctx.loop_phase_key(None, "QA") == "QA"
    assert ctx.loop_phase_key("BACK IMPLEMENT", "s01") == "IMPLEMENT"
    assert ctx.loop_phase_key("BACK CREATIVE", "s02") == "CREATIVE"


def test_resolve_decompose_override_beats_cli(
    monkeypatch, tmp_path: Path
) -> None:
    ctx = _load_ctx()
    monkeypatch.setenv("PROJECT_LOOP_DECOMPOSE_MODEL", "agy/claude-sonnet-4-6")
    out = ctx.resolve_loop_phase_model(
        phase="DECOMPOSE",
        armed_step="DECOMPOSE",
        cli_model="gpt",
        project_dir=tmp_path,
    )
    assert out["model"] == "agy/claude-sonnet-4-6"
    assert out["loop_phase"] == "DECOMPOSE"
    assert out["model_source"] == "phase_env"
    assert out["model_env"] == "PROJECT_LOOP_DECOMPOSE_MODEL"


def test_resolve_falls_back_to_cli_when_no_override(monkeypatch) -> None:
    ctx = _load_ctx()
    monkeypatch.delenv("PROJECT_LOOP_DECOMPOSE_MODEL", raising=False)
    monkeypatch.delenv("PROJECT_LOOP_IMPLEMENT_MODEL", raising=False)
    out = ctx.resolve_loop_phase_model(
        phase="BACK IMPLEMENT",
        armed_step="s01",
        cli_model="gpt",
    )
    assert out["model"] == "gpt"
    assert out["loop_phase"] == "IMPLEMENT"
    assert out["model_source"] == "cli"


def test_loop_phase_model_key_is_file_wins() -> None:
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from _lib import is_agent_model_file_wins_key

    assert is_agent_model_file_wins_key("PROJECT_LOOP_DECOMPOSE_MODEL")
    assert is_agent_model_file_wins_key("PROJECT_AGENT_VERIFY_MODEL")
    assert not is_agent_model_file_wins_key("EPIC_CHAIN_ROADMAP")


def test_loop_phase_key_done_beats_stale_audit() -> None:
    ctx = _load_ctx()
    assert ctx.loop_phase_key("DONE", "AUDIT") is None
    assert ctx.loop_phase_key("DONE", "QA") is None
    assert ctx.loop_phase_key("DONE", "REFLECT") is None
    assert ctx._phase_kind("DONE") == "done"
