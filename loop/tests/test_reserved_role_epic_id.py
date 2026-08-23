from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_reserved", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(mod)
    return mod


def _load_epic():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_lib

    return epic_lib


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_is_reserved_role_epic_id() -> None:
    from epic_paths import is_reserved_role_epic_id

    assert is_reserved_role_epic_id("back")
    assert is_reserved_role_epic_id("FRONT")
    assert is_reserved_role_epic_id("integration")
    assert is_reserved_role_epic_id("integ")
    assert not is_reserved_role_epic_id("T-HUB-005-simplify-docs")
    assert not is_reserved_role_epic_id("demo")
    assert not is_reserved_role_epic_id("demo-back")


def test_arm_rejects_decompose_back(tmp_path: Path) -> None:
    epic = _load_epic()
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-back/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | x | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-back/s01.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )
    out = epic.arm_active_context_from_decompose(
        tmp_path, "memory-bank/back/plan/decompose-back/index.md"
    )
    assert out["ok"] is False
    assert out["diagnostic_code"] == "epic_id_reserved"


def test_prepare_clears_reserved_role_arm(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. ok\n\n## Handoff\n- x\n")
    state = ctx.load_epic_state(tmp_path)
    state.update(
        {
            "active": True,
            "status": "armed",
            "armed_epic": "back",
            "armed_decompose": "memory-bank/back/plan/decompose-back/index.md",
            "armed_step": "s01",
        }
    )
    ctx.save_epic_state(tmp_path, state)

    out = ctx.prepare_session(tmp_path)
    assert out["ok"] is False
    assert out["halt"] is True
    assert out["diagnostic_code"] == "armed_role_slug"
    assert "role slug" in (out.get("reason") or "")

    after = ctx.load_epic_state(tmp_path)
    assert after.get("armed_epic") is None
    assert after.get("armed_decompose") is None
    assert after.get("status") == "halted"
    assert "armed_role_slug" in (after.get("diagnostic_codes") or [])


def test_check_after_clears_reserved_before_missing_index(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. ok\n\n## Handoff\n- x\n")
    state = ctx.load_epic_state(tmp_path)
    state.update(
        {
            "active": True,
            "status": "armed",
            "armed_epic": "back",
            "armed_decompose": "memory-bank/back/plan/decompose-back/index.md",
            "armed_step": "s01",
        }
    )
    ctx.save_epic_state(tmp_path, state)

    out = ctx.check_after(tmp_path, fingerprint_before="deadbeef")
    assert out["ok"] is False
    assert out["halt"] is True
    assert out["diagnostic_code"] == "armed_role_slug"
    assert "missing decompose index" not in (out.get("reason") or "")


def test_dag_validate_rejects_reserved_decompose() -> None:
    from dag import validate_manifest

    out = validate_manifest(
        {
            "schema": "loop-dag/v2",
            "pipeline": {"id": "portal"},
            "source": {"kind": "manifest", "artifacts": ["loop/dag/portal.yaml"]},
            "execution": {"autonomous": True},
            "nodes": [
                {
                    "id": "back",
                    "role": "BACK",
                    "decompose": "memory-bank/back/plan/decompose-back/index.md",
                    "depends_on": [],
                    "completion": {"type": "decompose"},
                    "action": "implement",
                }
            ],
        }
    )
    assert out["ok"] is False
    codes = {d["code"] for d in out["diagnostics"]}
    assert "epic_id_reserved" in codes


def test_dag_generate_rejects_gap_role_slug(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _write(
        tmp_path,
        "memory-bank/integration/gap/portal/gap-bad.md",
        "| BACK | decompose-back |\n| FRONT | decompose-front |\n",
    )
    out = ctx._cmd_dag_generate(tmp_path, "portal")
    assert out["ok"] is False
    codes = {d["code"] for d in out.get("diagnostics") or []}
    assert "epic_id_reserved" in codes
