from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

from loop.dag import adapt_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[2]


def _load_context_loop():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("t035_invariants_context_loop", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(module)
    return module


def _load_epic_lib():
    hooks = ROOT / ".claude" / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    spec = importlib.util.spec_from_file_location("t035_invariants_epic_lib", hooks / "epic_lib.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _manifest(nodes: list[dict]) -> dict:
    return {
        "schema": "loop-dag/v2",
        "pipeline": {"id": "portal"},
        "source": {"kind": "manifest", "artifacts": ["loop/dag/portal.yaml"]},
        "execution": {"autonomous": True},
        "nodes": nodes,
    }


def _work_node(node_id: str, depends_on: list[str] | None = None) -> dict:
    # node id may be a role lane ("back"); epic_id must not be a role slug.
    epic = "demo" if node_id in {"back", "front", "integration", "integ"} else node_id
    return {
        "id": node_id,
        "role": "BACK",
        "decompose": f"memory-bank/back/plan/decompose-{epic}/index.md",
        "depends_on": depends_on or [],
        "completion": {"type": "decompose"},
        "action": "implement",
    }


def _seed(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | step | pending |\n",
    )
    _write(cwd, "memory-bank/back/plan/decompose-demo/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "## load_now\n- `memory-bank/back/plan/decompose-demo/index.md`\n\n"
        "## Handoff BACK IMPLEMENT\n- **Следующий:** `BACK IMPLEMENT @s01`\n",
    )


@pytest.mark.parametrize(
    ("nodes", "codes"),
    [
        ([_work_node("back"), _work_node("back")], {"duplicate_node"}),
        ([_work_node("back", ["missing"])], {"missing_dependency"}),
        ([_work_node("back", ["back"])], {"cycle"}),
    ],
)
def test_invalid_graphs_never_ready(nodes: list[dict], codes: set[str]) -> None:
    result = validate_manifest(_manifest(nodes))

    assert result["ok"] is False
    assert codes <= {item["code"] for item in result["diagnostics"]}


def test_legacy_manifest_is_compatibility_only_and_not_autonomous() -> None:
    result = adapt_manifest(
        {
            "schema": "loop-dag/v1",
            "pipeline_id": "portal",
            "nodes": [{"id": "back", "role_dir": "back", "depends_on": []}],
        },
    )

    assert result["ok"] is True
    assert result["autonomous"] is False
    assert result["manifest"]["schema"] == "loop-dag/v2"
    assert any(item["code"] == "legacy_gap_inference" for item in result["diagnostics"])


def test_checkpoint_projection_rebuild_is_idempotent_and_does_not_invent_pending(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed(tmp_path)

    first = epic_lib.rebuild_epic_projection(tmp_path)
    second = epic_lib.rebuild_epic_projection(tmp_path)

    assert second["projection"]["projection_hash"] == first["projection"]["projection_hash"]
    assert second["projection"]["next_step"] == "s01"
    assert second["runtime"]["status"] == first["runtime"]["status"]

    state_path = tmp_path / ".claude/runtime/epic/state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["fanout_cursor"] = "s01"
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    resumed = epic_lib.rebuild_epic_projection(tmp_path)
    assert resumed["projection"]["next_step"] == "s01"


def test_checkpoint_conflict_halts_dag_without_promoting_cursor(tmp_path: Path) -> None:
    ctx = _load_context_loop()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- `memory-bank/back/plan/decompose-demo/index.md`\n"
        "- `memory-bank/front/plan/decompose-demo-front/index.md`\n",
    )
    _write(tmp_path, "loop/dag/portal.yaml", yaml.safe_dump(_manifest([_work_node("back")]), sort_keys=False))
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | step | pending |\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")

    state = ctx.load_epic_state(tmp_path)
    state.update({"dag_pipeline": "portal", "dag_done": ["unknown"], "dag_cursor": "missing"})
    ctx.save_epic_state(tmp_path, state)

    result = ctx._arm_dag_next(tmp_path, "portal")

    assert result["armed"] is True
    assert result.get("complete", False) is False
    assert result["node"] == "back"
    assert result["node"] != "missing"
    state_after = ctx.load_epic_state(tmp_path)
    assert state_after.get("dag_cursor") == "back"
