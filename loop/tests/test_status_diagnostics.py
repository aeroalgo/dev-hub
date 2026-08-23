from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_diagnostics", path)
    mod = importlib.util.module_from_spec(spec)
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_status_keeps_diagnostic_state_machine_readable(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n\n## Handoff\n- malformed\n")
    monkeypatch.delenv("EPIC_RUNTIME_CONFIG_JSON", raising=False)

    payload = ctx.status(tmp_path)

    assert payload["ok"] is True
    assert payload["recovery"]["diagnostics"]
    assert payload["session"]["exit_code"] is None


def test_status_reports_stale_owner_without_authorizing_kill(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s15.yaml](memory-bank/back/plan/decompose-x/s15.yaml)\n\n"
        "## Handoff\n- next: BACK IMPLEMENT @s15\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-x/s15.yaml", "step_id: s15\n")
    runtime = tmp_path / ".claude/runtime/epic"
    runtime.mkdir(parents=True)
    (runtime / "runner.json").write_text(
        '{"pid": 999999999, "host": "other", "started_at": "2026-08-05T00:00:00Z", "session_id": "sid", "selected_identity": "epic", "mode": "implement", "model": "model", "timeout_config": {}}',
        encoding="utf-8",
    )
    monkeypatch.delenv("EPIC_RUNTIME_CONFIG_JSON", raising=False)

    payload = ctx.status(tmp_path)

    assert payload["ok"] is True
    assert payload["runner"]["owner_alive"] is False
    assert "stale_owner" in payload["recovery"]["diagnostics"]
    assert "kill" not in payload["runner"]
