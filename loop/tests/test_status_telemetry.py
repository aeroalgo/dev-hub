from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_status", path)
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


def test_status_exposes_bounded_operational_groups(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s15.yaml](memory-bank/back/plan/decompose-x/s15.yaml)\n\n"
        "## Handoff\n- next: BACK IMPLEMENT @s15\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-x/s15.yaml", "step_id: s15\n")
    monkeypatch.delenv("EPIC_RUNTIME_CONFIG_JSON", raising=False)

    payload = ctx.status(tmp_path)

    assert payload["schema"] == "loop-status/v1"
    assert set(("runner", "session", "projection", "event", "gates", "dag", "recovery", "configuration")) <= set(payload)
    assert set(("effective", "sources")) <= set(payload["configuration"])
    assert "prompt" not in json.dumps(payload).lower()
    assert "secret" not in json.dumps(payload).lower()


def test_status_includes_session_event_and_owner_details(tmp_path: Path, monkeypatch) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [index.md](memory-bank/back/plan/decompose-x/index.md)\n\n"
        "## Handoff\n- next: BACK IMPLEMENT @s15\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-x/index.md", "# index\n")
    runtime = tmp_path / ".claude/runtime/epic"
    runtime.mkdir(parents=True)
    (runtime / "last-session.json").write_text(
        json.dumps({"updated_at": "2026-08-05T00:00:00Z", "exit_code": 124, "abort_kind": "timeout", "outcome": "timeout", "retry_count": 2, "log_file": "session.log"}),
        encoding="utf-8",
    )
    monkeypatch.delenv("EPIC_RUNTIME_CONFIG_JSON", raising=False)

    payload = ctx.status(tmp_path)

    assert payload["session"]["exit_code"] == 124
    assert payload["session"]["abort_kind"] == "timeout"
    assert payload["session"]["retry_count"] == 2
    assert payload["event"]["archive_count"] == 0
    assert payload["runner"]["owner"] is None
