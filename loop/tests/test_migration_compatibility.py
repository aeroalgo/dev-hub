from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))
if str(ROOT / "loop") not in sys.path:
    sys.path.insert(0, str(ROOT / "loop"))

from dag import migrate_manifest  # noqa: E402
from epic_events import migrate_event_log  # noqa: E402


def test_event_migration_is_idempotent_and_writes_replay_report(tmp_path: Path) -> None:
    event_path = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    event_path.parent.mkdir(parents=True)
    archive = event_path.parent / "archive-legacy.jsonl"
    archive.write_text(
        json.dumps({"kind": "qa_pass", "artifact": "memory-bank/back/qa/one.yaml"}) + "\n",
        encoding="utf-8",
    )
    event_path.write_text(
        json.dumps({"kind": "bugfix_done", "artifact": "memory-bank/back/bugfix/two.md"}) + "\n",
        encoding="utf-8",
    )

    first = migrate_event_log(event_path, epic_id="demo", cwd=tmp_path)
    second = migrate_event_log(event_path, epic_id="demo", cwd=tmp_path)

    assert first["ok"] is True
    assert first["migrated"] == 2
    assert first["replay_digest"] == second["replay_digest"]
    assert second["migrated"] == 0
    assert [event["seq"] for event in first["events"]] == [1, 2]
    assert all(event["metadata"]["migrated_from"] == "loop-event/v1" for event in first["events"])
    assert json.loads((tmp_path / ".claude/runtime/epic/migration-v1.json").read_text())["replay_digest"] == first["replay_digest"]


def test_state_migration_exposes_explicit_marker(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("epic_lib_migration", HOOKS / "epic_lib.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    index = tmp_path / "memory-bank/back/plan/decompose-demo/index.md"
    index.parent.mkdir(parents=True)
    index.write_text("| step_id | title | status |\n| :--- | :--- | :--- |\n| **s01** | demo | pending |\n", encoding="utf-8")
    (tmp_path / "memory-bank/activeContext.md").write_text("## load_now\n- x\n\n## Handoff\n- next\n", encoding="utf-8")
    state_path = tmp_path / ".claude/runtime/epic/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "status": "running"}), encoding="utf-8")

    state = module.rebuild_epic_projection(tmp_path)

    assert state["state_migrated"] is True
    assert state["state_rebuilt"] is False


def test_dag_migration_requires_explicit_compatibility_mode() -> None:
    legacy = {
        "schema": "loop-dag/v1",
        "pipeline_id": "demo",
        "nodes": [{"id": "back", "role_dir": "back", "decompose": "memory-bank/back/plan/decompose-demo/index.md"}],
    }

    blocked = migrate_manifest(legacy)
    migrated = migrate_manifest(legacy, compatibility_mode=True)

    assert blocked["ok"] is False
    assert any(item["code"] == "compatibility_mode_required" for item in blocked["diagnostics"])
    assert migrated["ok"] is True
    assert migrated["migrated"] is True
    assert migrated["autonomous"] is False
    assert migrated["manifest"]["schema"] == "loop-dag/v2"
