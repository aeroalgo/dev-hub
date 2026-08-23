from __future__ import annotations

from pathlib import Path

from loop.tests.test_dag_scheduler import _load_ctx, _manifest, _write, _work_node


def test_gap_back_front_close_journey_waits_for_close_evidence(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    nodes = [
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
    ]
    _write(tmp_path, "loop/dag/portal.yaml", _manifest(nodes))
    for role, epic in (("back", "demo"), ("front", "demo-front")):
        _write(
            tmp_path,
            f"memory-bank/{role}/plan/decompose-{epic}/index.md",
            "| step_id | title | status |\n|---|---|---|\n| **s01** | [s01-step.yaml](s01-step.yaml) | pending |\n",
        )
        _write(tmp_path, f"memory-bank/{role}/plan/decompose-{epic}/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")

    out = ctx._arm_dag_next(tmp_path, "portal")
    assert out["node"] == "back"

    state = ctx.load_epic_state(tmp_path)
    state.update({"dag_done": ["back", "front"], "dag_cursor": None})
    ctx.save_epic_state(tmp_path, state)
    out = ctx._arm_dag_next(tmp_path, "portal")
    assert out["armed"] is False
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert out["blocked"]["close"] == ["completion_contract"]

    _write(
        tmp_path,
        "memory-bank/integration/gap/portal/gap-close.yaml",
        "status: closed\nintegration_gate: pass\n",
    )
    out = ctx._arm_dag_next(tmp_path, "portal")
    assert out["complete"] is True
    assert out["dag_done"] == ["back", "close", "front"]


def test_state_loss_rebuilds_cursor_from_completion_evidence(tmp_path: Path) -> None:
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
        "| step_id | title | status |\n|---|---|---|\n",
    )
    _write(
        tmp_path,
        "memory-bank/front/plan/decompose-demo-front/index.md",
        "| step_id | title | status |\n|---|---|---|\n| s01 | step | pending |\n",
    )
    state = ctx.load_epic_state(tmp_path)
    state["dag_done"] = []
    ctx.save_epic_state(tmp_path, state)

    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["ok"] is True
    assert out["complete"] is True
    assert out["armed"] is False
    assert out["dag_done"] == ["back", "front"]
