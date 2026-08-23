from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_context_loop():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("t035_acceptance_context_loop", path)
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
    spec = importlib.util.spec_from_file_location("t035_acceptance_epic_lib", hooks / "epic_lib.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _manifest(nodes: list[dict]) -> str:
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


def _seed_state_recovery(cwd: Path) -> None:
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


def test_acceptance_matrix_rejects_invalid_dag_without_ready_path() -> None:
    from loop.dag import validate_manifest

    manifest = {
        "schema": "loop-dag/v2",
        "pipeline": {"id": "portal"},
        "source": {"kind": "manifest", "artifacts": ["loop/dag/portal.yaml"]},
        "execution": {"autonomous": True},
        "nodes": [
            _work_node("back", "memory-bank/back/plan/decompose-demo/index.md"),
            _work_node("front", "../escape/index.md", ["missing"]),
        ],
    }

    result = validate_manifest(manifest)

    assert result["ok"] is False
    assert {item["code"] for item in result["diagnostics"]} >= {
        "missing_dependency",
        "path_invalid",
    }


def test_acceptance_gate_waits_for_close_completion_evidence(tmp_path: Path) -> None:
    ctx = _load_context_loop()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n- old\n")
    _write(
        tmp_path,
        "loop/dag/portal.yaml",
        _manifest(
            [
                _work_node("back", "memory-bank/back/plan/decompose-demo/index.md"),
                _work_node("front", "memory-bank/front/plan/decompose-demo-front/index.md", ["back"]),
                {
                    "id": "close",
                    "role": "INTEG",
                    "artifact": "memory-bank/integration/gap/portal/gap-close.yaml",
                    "depends_on": ["front"],
                    "completion": {"type": "artifact"},
                    "action": "close",
                },
            ],
        ),
    )
    for role, epic in (("back", "demo"), ("front", "demo-front")):
        _write(
            tmp_path,
            f"memory-bank/{role}/plan/decompose-{epic}/index.md",
            "| step_id | title | status |\n|---|---|---|\n| **s01** | step | pending |\n",
        )
        _write(
            tmp_path,
            f"memory-bank/{role}/plan/decompose-{epic}/s01-step.yaml",
            "schema: epic-decompose/v1\nstep_id: s01\n",
        )

    first = ctx._arm_dag_next(tmp_path, "portal")
    assert first["node"] == "back"

    state = ctx.load_epic_state(tmp_path)
    state.update({"dag_done": ["back", "front"], "dag_cursor": None})
    ctx.save_epic_state(tmp_path, state)
    blocked = ctx._arm_dag_next(tmp_path, "portal")
    assert blocked["diagnostic"]["code"] == "dag_blocked"
    assert blocked["blocked"]["close"] == ["completion_contract"]

    _write(tmp_path, "memory-bank/integration/gap/portal/gap-close.yaml", "status: closed\nintegration_gate: pass\n")
    complete = ctx._arm_dag_next(tmp_path, "portal")
    assert complete["complete"] is True
    assert complete["dag_done"] == ["back", "close", "front"]


def test_acceptance_rebuild_is_deterministic_after_state_loss(tmp_path: Path) -> None:
    epic_lib = _load_epic_lib()
    _seed_state_recovery(tmp_path)

    initial = epic_lib.rebuild_epic_projection(tmp_path)
    (tmp_path / ".claude/runtime/epic/state.json").unlink()
    rebuilt = epic_lib.rebuild_epic_projection(tmp_path)

    assert rebuilt["projection"]["projection_hash"] == initial["projection"]["projection_hash"]
    assert rebuilt["projection"]["next_step"] == "s01"
    assert "state_rebuilt" in rebuilt["diagnostic_codes"]
    json.loads((tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8"))
