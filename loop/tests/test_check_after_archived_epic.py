"""check_after must disarm when armed decompose moved to archive/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    loop = str(ROOT / "loop")
    if loop not in sys.path:
        sys.path.insert(0, loop)
    spec = importlib.util.spec_from_file_location(
        "context_loop_archived", ROOT / "loop" / "context_loop.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_archived_epic(tmp_path: Path, epic: str) -> str:
    active_decompose = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    archive_decompose = f"memory-bank/archive/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / archive_decompose,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "source_md: index.md\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  title: one\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: completed\n",
    )
    _write(
        tmp_path / "memory-bank/activeContext.md",
        "## load_now\n"
        f"1. [{epic}](back/plan/decompose-{epic}/index.yaml)\n\n"
        f"## Handoff — {epic}\n"
        "- **Режим/шаг:** `BACK ARCHIVE NOW` / ARCHIVE NOW completed.\n"
        "- **Дальше:** следующий эпик.\n",
    )
    ctx = _load_ctx()
    st = ctx.load_epic_state(tmp_path)
    st.update(
        {
            "active": True,
            "status": "running",
            "armed_epic": epic,
            "armed_decompose": active_decompose,
            "armed_step": "QA",
            "phase": "QA",
        }
    )
    ctx.save_epic_state(tmp_path, st)
    return active_decompose


def test_check_after_completes_when_decompose_archived(tmp_path: Path) -> None:
    epic = "T-HUB-022-runtime-pydantic-schemas"
    _seed_archived_epic(tmp_path, epic)
    ctx = _load_ctx()
    out = ctx.check_after(tmp_path, fingerprint_before="before-fp")
    assert out.get("ok") is True
    assert out.get("complete") is True
    assert out.get("stop") == "ARCHIVE_DONE"
    st = ctx.load_epic_state(tmp_path)
    assert st.get("active") is False
    assert st.get("status") == "complete"
    assert st.get("armed_decompose") is None
    assert st.get("armed_epic") is None


def test_load_decompose_steps_fail_closed_reads_archive_mirror(tmp_path: Path) -> None:
    epic = "T-HUB-022-runtime-pydantic-schemas"
    active = f"memory-bank/back/plan/decompose-{epic}/index.yaml"
    archive = f"memory-bank/archive/back/plan/decompose-{epic}/index.yaml"
    _write(
        tmp_path / archive,
        "schema: epic-decompose-index/v1\n"
        f"plan_id: {epic}\n"
        "source_md: index.md\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  title: one\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: completed\n",
    )
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from epic import load_decompose_steps_fail_closed

    loaded = load_decompose_steps_fail_closed(tmp_path, active)
    assert loaded.get("ok") is True
    assert loaded.get("steps")[0]["id"] == "s01"
