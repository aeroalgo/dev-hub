from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
def _load_epic_lib():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic

    return epic


def _seed_index(tmp_path: Path, *, next_step: bool = True) -> tuple[Path, Path]:
    index_dir = (
        tmp_path
        / "memory-bank/back/plan/decompose-demo"
    )
    index_dir.mkdir(parents=True)
    rows = [
        "| **s06** | [s06-old.yaml](s06-old.yaml) | BACK IMPLEMENT | completed |",
    ]
    steps = [
        {
            "id": "s06",
            "file": "s06-old.yaml",
            "next_phase": "BACK IMPLEMENT",
            "title": "old step",
            "status": "completed",
        }
    ]
    if next_step:
        rows.append(
            "| **s07** | [s07-next.yaml](s07-next.yaml) | BACK IMPLEMENT | pending |"
        )
        steps.append(
            {
                "id": "s07",
                "file": "s07-next.yaml",
                "next_phase": "BACK IMPLEMENT",
                "title": "next step",
                "status": "pending",
            }
        )
    import yaml

    ypath = index_dir / "index.yaml"
    ypath.write_text(
        yaml.safe_dump(
            {"schema": "epic-decompose-index/v1", "plan_id": "demo", "steps": steps},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    md_path = index_dir / "index.md"
    md_path.write_text(
        "**Plan ID:** demo\n\n"
        "| Step | Shard | Phase | Status |\n"
        "|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    (index_dir / "s07-next.yaml").write_text("step_id: s07\n", encoding="utf-8")
    active = tmp_path / "memory-bank/activeContext.md"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text("## load_now\n- old\n\n## Handoff\n- old\n", encoding="utf-8")
    return ypath, active


def _mark(lib, tmp_path: Path, status: str = "completed") -> dict:
    return lib.mark_index_step_status(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "s06",
        status,
    )


def test_mark_index_advance_rewrites_active_context(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _, active = _seed_index(tmp_path)

    result = _mark(lib, tmp_path)

    assert result["activeContext_rewritten"] is True
    assert result["next_step"] == "s07"
    body = active.read_text(encoding="utf-8")
    assert "s07-next.yaml" in body
    assert "index.yaml" in body
    assert "](back/plan/decompose-demo/index.md)" not in body
    assert "## Handoff" in body


def test_mark_index_advance_updates_armed_step(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _seed_index(tmp_path)

    result = _mark(lib, tmp_path)

    state = json.loads(
        (tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8")
    )
    assert result["armed_step_updated"] is True
    assert state["armed_step"] == "s07"
    assert state["pending_fingerprint_before"] is None


def test_mark_index_advance_skips_when_no_next_step(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _, active = _seed_index(tmp_path, next_step=False)
    before = active.read_text(encoding="utf-8")

    result = _mark(lib, tmp_path)

    assert result["activeContext_rewritten"] is False
    assert result["next_step"] is None
    assert active.read_text(encoding="utf-8") == before


def test_mark_index_advance_skips_when_status_not_completed(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _, active = _seed_index(tmp_path)
    before = active.read_text(encoding="utf-8")

    result = _mark(lib, tmp_path, status="active")

    assert result["activeContext_rewritten"] is False
    assert result["armed_step_updated"] is False
    assert active.read_text(encoding="utf-8") == before


def test_mark_index_advance_soft_fail_on_write_error(
    tmp_path: Path, monkeypatch
) -> None:
    lib = _load_epic_lib()
    _seed_index(tmp_path)

    def fail_write(*args, **kwargs):
        raise OSError("activeContext unavailable")

    monkeypatch.setattr(lib, "atomic_write_text", fail_write)

    result = _mark(lib, tmp_path)

    assert result["ok"] is True
    assert result["activeContext_rewritten"] is False
    assert result["advance_diagnostic"]["ok"] is False
    assert "activeContext unavailable" in result["advance_diagnostic"]["error"]


def test_mark_index_advance_result_keys(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _seed_index(tmp_path)

    result = _mark(lib, tmp_path)

    assert {
        "next_step",
        "activeContext_rewritten",
        "armed_step_updated",
    }.issubset(result)
