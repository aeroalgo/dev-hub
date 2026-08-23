from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

import yaml

from loop.dag import validate_manifest
from loop.tests.test_dag_scheduler import _load_ctx, _write


MANIFEST = Path(__file__).resolve().parents[1] / "dag" / "integ-demo.yaml"
NODE_IDS = {"gap_close", "back_impl", "front_impl", "integ_verify"}


def _write_decompose_index(cwd: Path, rel: str, role: str) -> None:
    index = """schema: epic-decompose-index/v1
plan_id: demo
source_md: index.md
status_canon: index.yaml
steps:
- id: s01
  file: s01-demo.yaml
  next_phase: BACK IMPLEMENT
  title: demo step
  status: pending
"""
    _write(cwd, rel, index)
    _write(
        cwd,
        str(Path(rel).parent / "s01-demo.yaml"),
        f"schema: epic-decompose/v1\nrole: {role}\nstep_id: s01\n",
    )


def _node_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    values = (*args, *kwargs.values())
    for value in values:
        if isinstance(value, dict) and value.get("id") in NODE_IDS:
            return str(value["id"])
        if isinstance(value, str) and value in NODE_IDS:
            return value
    return None


def test_dag_manifest_validates() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    result = validate_manifest(manifest)

    assert result["ok"] is True
    assert result["diagnostics"] == []


def test_dag_integ_journey_full(tmp_path: Path, monkeypatch: Any) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")
    _write(tmp_path, "loop/dag/integ-demo.yaml", MANIFEST.read_text(encoding="utf-8"))
    _write_decompose_index(
        tmp_path,
        "memory-bank/back/plan/decompose-demo-back/index.yaml",
        "BACK",
    )
    _write_decompose_index(
        tmp_path,
        "memory-bank/front/plan/decompose-demo-front/index.yaml",
        "FRONT",
    )
    _write_decompose_index(
        tmp_path,
        "memory-bank/integ/plan/decompose-demo-verify/index.yaml",
        "INTEG",
    )

    completed: set[str] = set()
    def fake_arm_target(
        root: Path,
        dag: dict[str, Any],
        node: dict[str, Any],
        done: set[str],
        ready: list[str],
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "armed": True,
            "node": str(node["id"]),
            "ready": ready,
            "execution": "sequential",
        }

    monkeypatch.setattr(ctx, "_dag_arm_target", fake_arm_target)

    original_node_status = ctx._node_status

    def fake_node_status(*args: Any, **kwargs: Any) -> str:
        node = _node_id(args, kwargs)
        if node in completed:
            return "done"
        if node in {"back_impl", "front_impl", "integ_verify"}:
            return "pending"
        return original_node_status(*args, **kwargs)

    monkeypatch.setattr(ctx, "_node_status", fake_node_status)

    out = ctx.dag_fanout(tmp_path)
    assert out["ok"] is True
    assert out["armed"] is False
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert "gap_close" in out["blocked"]

    _write(
        tmp_path,
        "memory-bank/integ/plan/decompose-demo-gap/index.yaml",
        "status: closed\nintegration_gate: pass\n",
    )
    out = ctx.dag_fanout(tmp_path)
    assert out["ok"] is True, out
    assert out["armed"] is True, out
    assert out["node"] == "back_impl"

    completed.add("back_impl")
    out = ctx.dag_fanout(tmp_path)
    assert out["ok"] is True
    assert out["armed"] is True, out
    assert out["node"] == "front_impl"

    completed.add("front_impl")
    out = ctx.dag_fanout(tmp_path)
    assert out["ok"] is True
    assert out["armed"] is True, out
    assert out["node"] == "integ_verify"

    completed.add("integ_verify")
    out = ctx.dag_fanout(tmp_path)
    assert out["ok"] is True
    assert out["complete"] is True
    assert out["armed"] is False


def test_dag_manifest_fixture_is_copied_from_repository(tmp_path: Path) -> None:
    destination = tmp_path / "loop" / "dag" / "integ-demo.yaml"
    destination.parent.mkdir(parents=True)
    shutil.copyfile(MANIFEST, destination)

    assert destination.read_text(encoding="utf-8") == MANIFEST.read_text(encoding="utf-8")
