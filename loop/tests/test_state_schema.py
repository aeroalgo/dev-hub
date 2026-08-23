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
    spec = importlib.util.spec_from_file_location("epic_lib_state_schema", HOOKS / "epic_lib.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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


def test_rebuilt_state_has_nested_v2_sections_without_sensitive_values(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)

    state = epic_lib.rebuild_epic_projection(tmp_path)
    raw = json.loads((tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8"))

    assert raw["state_schema_version"] == "loop-state/v2"
    assert set(("projection", "runtime", "dag", "gate_snapshot")) <= raw.keys()
    assert raw["projection"]["schema_version"] == "loop-projection/v2"
    assert raw["runtime"]["status"] == state["status"]
    assert raw["gate_snapshot"] == raw["projection"]["gates"]
    serialized = json.dumps(raw, ensure_ascii=False)
    assert "prompt" not in serialized.lower()
    assert "secret" not in serialized.lower()
    assert "events.jsonl" not in serialized


def test_legacy_flat_aliases_are_read_and_migrated(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)
    state_path = tmp_path / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"active": True, "status": "running", "dag_pipeline": "demo", "fanout_cursor": "node-a"}),
        encoding="utf-8",
    )

    state = epic_lib.rebuild_epic_projection(tmp_path)

    assert state["runtime"]["active"] is True
    assert state["runtime"]["status"] == "running"
    assert state["dag"]["pipeline_id"] == "demo"
    assert state["dag"]["cursor"] == "node-a"
    assert "state_migrated" in state["diagnostic_codes"]
