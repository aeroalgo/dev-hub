from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_ctx():
    if str(ROOT / "loop") not in sys.path:
        sys.path.insert(0, str(ROOT / "loop"))
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import context_loop
    return context_loop


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _seed(cwd: Path) -> None:
    _write(
        cwd,
        "memory-bank/activeContext.md",
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: x\n"
        "step_id: s01\n"
        "---\n\n"
        "## load_now\n"
        "1. [s01.yaml](back/plan/decompose-x/s01.yaml) — work shard.\n\n"
        "## Handoff BACK IMPLEMENT — s01\n"
        "- **Следующий:** `BACK IMPLEMENT @s01`\n",
    )
    _write(cwd, "memory-bank/back/plan/decompose-x/s01.yaml", "step_id: s01\n")


def test_shape_diagnostics_are_stable_codes() -> None:
    _load_ctx()
    from epic import validate_active_context_shape

    errors = validate_active_context_shape("## Handoff\n- EPIC_DONE\n")

    assert errors == ["missing_handoff_frontmatter", "missing_load_now"]


def test_shape_diagnostics_distinguish_duplicate_sections() -> None:
    from epic import validate_active_context_shape

    errors = validate_active_context_shape(
        "## load_now\n- x\n\n## load_now\n- y\n\n"
        "## Handoff one\n- x\n\n## Handoff two\n- y\n\n"
        "## done\n- x\n\n## done\n- y\n"
    )

    assert errors == [
        "missing_handoff_frontmatter",
        "multiple_load_now",
        "multiple_handoff",
        "multiple_done",
    ]


def test_active_context_shape_is_machine_halt(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- broken\n\n## Handoff one\n- x\n\n## Handoff two\n- y\n",
    )

    out = ctx.prepare_session(tmp_path, model="test-model")
    assert out["ok"] is False
    assert out["halt"] is True
    assert out["diagnostic_codes"]


def test_valid_context_is_not_degraded(tmp_path: Path) -> None:
    ctx = _load_ctx()
    _seed(tmp_path)
    out = ctx.prepare_session(tmp_path, model="test-model")

    assert out["ok"] is True
    assert out["degraded"] is False
