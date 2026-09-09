from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_need_human", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def _write(tmp_path: Path, rel: str, text: str) -> None:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

def test_record_abort_need_human_is_not_transient(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. [s02](s02.yaml)\n")
    rel = "/".join([".claude", "runtime", "epic", "state.json"])
    _write(tmp_path, rel, json.dumps({"status": "running", "active": True, "armed_step": "s02", "armed_epic": "x", "session_id": "runner-current", "need_human": "semantic_ownership_mismatch"}))
    log = tmp_path / "session.log"
    log.write_text("SESSION_START session=runner-current mode=headless command=codex\n{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"done\"}}\nSESSION_END session=runner-current exit_code=0\n", encoding="utf-8")
    out = ctx.record_abort(tmp_path, log_path=log, exit_code=0, runtime="codex")
    assert out["ok"] is False
    assert out["retryable"] is False
    assert out["reason"] == "NEED_HUMAN: semantic_ownership_mismatch"

