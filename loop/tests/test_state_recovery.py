from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_epic_lib():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("epic_lib_state_recovery", HOOKS / "epic_lib.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_context_loop():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_state_recovery", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _seed(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **s01** | [s01-demo.yaml](s01-demo.yaml) | pending |\n",
    )
    _write(cwd, "memory-bank/back/plan/decompose-demo/s01-demo.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-demo/index.md`\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT @s01`\n",
    )


def test_rebuilds_missing_state_from_canonical_sources(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)

    first = epic_lib.rebuild_epic_projection(tmp_path)
    (tmp_path / ".claude/runtime/epic/state.json").unlink()
    rebuilt = epic_lib.rebuild_epic_projection(tmp_path)

    assert rebuilt["projection"]["projection_hash"] == first["projection"]["projection_hash"]
    assert rebuilt["projection"]["epic_id"] == "demo"
    assert rebuilt["projection"]["next_step"] == "s01"
    assert "state_rebuilt" in rebuilt["diagnostic_codes"]


def test_rebuilds_malformed_state_and_preserves_runtime_metadata(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    state_path = tmp_path / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"active": True, "status": "degraded", "retry_count": 2})[:-1],
        encoding="utf-8",
    )

    rebuilt = epic_lib.rebuild_epic_projection(tmp_path)

    assert rebuilt["runtime"]["active"] is False
    assert rebuilt["runtime"]["status"] == "idle"
    assert "state_schema_invalid" in rebuilt["diagnostic_codes"]
    assert rebuilt["projection"]["next_step"] == "s01"


def test_cursor_rebuild_does_not_switch_epic(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    state_path = tmp_path / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"armed_epic": "other", "armed_decompose": "memory-bank/back/plan/decompose-other/index.md", "fanout_cursor": "other-node"}),
        encoding="utf-8",
    )

    rebuilt = epic_lib.rebuild_epic_projection(tmp_path)

    assert rebuilt["projection"]["epic_id"] == "other"
    assert rebuilt["projection"]["dag_node_id"] == "other-node"
    assert rebuilt["dag"]["cursor"] == "other-node"


def test_halt_reason_set_on_dirty_resume(tmp_path: Path) -> None:
    context_loop = _load_context_loop()
    _seed(tmp_path)
    log = tmp_path / "session.log"
    log.write_text(
        '{"type":"result","terminal_reason":"api_error","result":"API Error: terminated"}\n',
        encoding="utf-8",
    )

    out = context_loop.record_abort(tmp_path, log_path=log, exit_code=1)
    state = json.loads((tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8"))

    assert out["retryable"] is True
    assert state["halt_reason"] == "API Error: terminated"


def test_halt_reason_idle_after_clean_stop(tmp_path: Path) -> None:
    context_loop = _load_context_loop()
    _seed(tmp_path)
    state_path = tmp_path / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"status":"running", "halt_reason":null}\n', encoding="utf-8")
    log = tmp_path / "session.log"
    log.write_text("clean stop\n", encoding="utf-8")

    context_loop.record_abort(tmp_path, log_path=log, exit_code=0)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["halt_reason"] is None
