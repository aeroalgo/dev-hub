"""Handoff SoT vs auto-reconciled post-implement lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
LOOP = ROOT / "loop"
for p in (str(HOOKS), str(LOOP)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_finished_artifact(path: Path, text: str) -> None:
    from loop.tests.lifecycle_helpers import record_finished_artifact

    _write(path, text)
    cwd = next(parent.parent for parent in path.parents if parent.name == "memory-bank")
    record_finished_artifact(cwd, path)


def _load_ctx():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("context_loop_handoff", LOOP / "context_loop.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mb_paths_for_prompt_are_absolute(tmp_path: Path) -> None:
    ctx = _load_ctx()
    ac = tmp_path / "memory-bank/activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text("## load_now\n", encoding="utf-8")
    plan = tmp_path / "memory-bank/back/plan/demo/md/plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# plan\n", encoding="utf-8")
    paths = ctx.mb_paths_for_prompt(
        tmp_path,
        ["memory-bank/back/plan/demo/md/plan.md"],
    )
    assert paths[0] == str(ac.resolve())
    assert paths[1] == str(plan.resolve())


def test_projection_from_state_when_no_decompose_index(tmp_path: Path) -> None:
    from epic import load_epic_state, rebuild_epic_projection, save_epic_state

    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n- [plan](back/plan/T-060/md/plan.md)\n\n"
        "## Handoff BACK DECOMPOSE — T-060\n",
    )
    st = load_epic_state(tmp_path)
    st.update(
        {
            "armed_epic": "T-060",
            "armed_step": "DECOMPOSE",
            "role": "BACK",
            "armed_decompose": None,
        }
    )
    save_epic_state(tmp_path, st)
    projection = rebuild_epic_projection(tmp_path)
    proj = projection.get("projection") or {}
    assert proj.get("epic") == "T-060"
    assert proj.get("phase") == "DECOMPOSE"
    assert proj.get("next_step") == "DECOMPOSE"
