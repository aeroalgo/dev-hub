from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_scheduler", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(mod)
    return mod


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _manifest(nodes: list[dict]) -> str:
    import yaml

    return yaml.safe_dump(
        {
            "schema": "loop-dag/v2",
            "pipeline": {"id": "portal"},
            "source": {"kind": "manifest", "artifacts": ["loop/dag/portal.yaml"]},
            "execution": {"autonomous": True},
            "nodes": nodes,
        },
        sort_keys=False,
    )


def _work_node(node_id: str, target: str, depends_on: list[str] | None = None) -> dict:
    return {
        "id": node_id,
        "role": "BACK",
        "decompose": target,
        "depends_on": depends_on or [],
        "completion": {"type": "decompose"},
        "action": "implement",
    }


def test_scheduler_arms_one_ready_node_in_stable_order(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    _write(
        tmp_path,
        "loop/dag/portal.yaml",
        _manifest(
            [
                _work_node("z-back", "memory-bank/back/plan/decompose-z/index.md"),
                _work_node("a-back", "memory-bank/back/plan/decompose-a/index.md"),
            ]
        ),
    )
    for name in ("z", "a"):
        _write(
            tmp_path,
            f"memory-bank/back/plan/decompose-{name}/index.md",
            "| step_id | title | status |\n|---|---|---|\n| **s01** | [s01-step.yaml](s01-step.yaml) | pending |\n",
        )
        _write(tmp_path, f"memory-bank/back/plan/decompose-{name}/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")

    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["ok"] is True
    assert out["armed"] is True
    assert out["node"] == "a-back"
    assert out["ready"] == ["a-back", "z-back"]
    assert out["execution"] == "sequential"


def test_scheduler_reports_dependency_reasons_when_blocked(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    _write(
        tmp_path,
        "loop/dag/portal.yaml",
        _manifest(
            [
                _work_node("back", "memory-bank/back/plan/decompose-demo/index.md"),
                _work_node("front", "memory-bank/front/plan/decompose-demo-front/index.md", ["back"]),
            ]
        ),
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | [s01-step.yaml](s01-step.yaml) | pending |\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")
    _write(
        tmp_path,
        "memory-bank/front/plan/decompose-demo-front/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | [s01-step.yaml](s01-step.yaml) | pending |\n",
    )
    _write(tmp_path, "memory-bank/back/plan/decompose-demo/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")

    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["ok"] is True
    assert out["armed"] is True
    assert out["node"] == "back"

    state = ctx.load_epic_state(tmp_path)
    state.update({"dag_done": [], "dag_cursor": None})
    ctx.save_epic_state(tmp_path, state)
    ctx._dag_mark_completed = lambda _root, _dag: set()
    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["armed"] is True
    assert out["node"] == "back"

    state = ctx.load_epic_state(tmp_path)
    state.update({"dag_done": [], "dag_cursor": "front"})
    ctx.save_epic_state(tmp_path, state)
    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["armed"] is False
    assert out["complete"] is False
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert out["blocked"]["front"] == ["back"]


def test_selected_missing_manifest_is_fail_closed(tmp_path: Path) -> None:
    ctx = _load_ctx()

    out = ctx._arm_dag_next(tmp_path, "missing")

    assert out["ok"] is False
    assert out["diagnostic"]["code"] == "dag_manifest_missing"
