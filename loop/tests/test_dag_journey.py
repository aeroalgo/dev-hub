from __future__ import annotations

from pathlib import Path

from loop.tests.test_dag_scheduler import _load_ctx, _manifest, _write, _work_node


def test_gap_back_front_close_journey_waits_for_close_evidence(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    nodes = [
        _work_node("back", "memory-bank/back/plan/demo/yaml/decompose-index.yaml"),
        _work_node("front", "memory-bank/front/plan/demo-front/yaml/decompose-index.yaml", ["back"]),
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
            f"memory-bank/{role}/plan/{epic}/yaml/decompose-index.yaml",
            "schema: epic-decompose-index/v1\nplan_id: " + epic + "\nsteps:\n  - id: s01\n    file: s01-step.yaml\n    status: pending\n",
        )
        _write(tmp_path, f"memory-bank/{role}/plan/{epic}/yaml/steps/s01-step.yaml", "schema: epic-decompose/v1\nstep_id: s01\n")

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
                _work_node("back", "memory-bank/back/plan/demo/yaml/decompose-index.yaml"),
                _work_node("front", "memory-bank/front/plan/demo-front/yaml/decompose-index.yaml", ["back"]),
            ]
        ),
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/demo/yaml/decompose-index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n  - id: s01\n    file: s01.yaml\n    status: completed\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/demo/yaml/steps/s01.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/audit/demo/audit-20260901-test.yaml",
        "verdict: PASS\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/qa/demo/qa-20260901-test.yaml",
        "verdict: pass\n",
    )
    _write(
        tmp_path,
        "memory-bank/front/plan/demo-front/yaml/decompose-index.yaml",
        "schema: epic-decompose-index/v1\nplan_id: demo-front\nsteps:\n  - id: s01\n    file: s01.yaml\n    status: pending\n",
    )
    _write(
        tmp_path,
        "memory-bank/front/plan/demo-front/yaml/steps/s01.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    state = ctx.load_epic_state(tmp_path)
    state["dag_done"] = []
    ctx.save_epic_state(tmp_path, state)

    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["ok"] is True
    assert out["armed"] is True
    assert out["node"] == "front"
