from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _hooks() -> None:
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))


def _write(cwd: Path, rel: str, body: str) -> Path:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _decompose_doc(*, step_id: str = "s01", plan_id: str = "T-004") -> str:
    return (
        "schema: epic-decompose/v1\n"
        "role: back\n"
        f"step_id: {step_id}\n"
        f"plan_id: {plan_id}\n"
        "title: hub alias\n"
        "next_phase: BACK IMPLEMENT\n"
        "needs_creative: 'no'\n"
        "goal: seed hub\n"
        "context:\n"
        "  files:\n"
        "  - core/x.py\n"
        "checkpoints:\n"
        "- id: cp1\n"
        "  criterion: c\n"
        "  verify: 'true'\n"
    )


def _implement_doc(*, step_id: str = "s03", status: str = "in_progress") -> str:
    cp_status = "done" if status == "completed" else "pending"
    return (
        "schema: epic-implement/v1\n"
        "role: back\n"
        f"step_id: {step_id}\n"
        "plan_id: T-004\n"
        "title: lock\n"
        f"status: {status}\n"
        "date: '2026-08-14'\n"
        "checkpoints:\n"
        f"- id: cp1\n  criterion: c\n  status: {cp_status}\n"
    )


def _index_pair(cwd: Path, *, status: str = "pending") -> None:
    _write(
        cwd,
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.yaml",
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-004\n"
        "source_md: index.md\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s03\n"
        "  file: s03-gg-interprocess-lock.yaml\n"
        "  next_phase: BACK CREATIVE\n"
        "  title: lock\n"
        f"  status: {status}\n",
    )
    _write(
        cwd,
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.md",
        "**Plan ID:** T-004\n\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        f"| **s03** | lock | BACK CREATIVE | {status} |\n",
    )


def test_epic_id_from_decompose_path_reads_folder_not_shard_stem() -> None:
    _hooks()
    from epic_paths import epic_id_from_decompose_path

    shard = (
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/"
        "s01-llm-async.yaml"
    )
    assert epic_id_from_decompose_path(shard) == "T-004-tg-async-rps"
    assert (
        epic_id_from_decompose_path(
            "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.yaml"
        )
        == "T-004-tg-async-rps"
    )


def test_seed_implement_uses_folder_epic_when_plan_id_differs(tmp_path: Path) -> None:
    _hooks()
    from epic_yaml import seed_implement_from_decompose

    rel = (
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/"
        "s01-llm-async.yaml"
    )
    _write(tmp_path, rel, _decompose_doc())

    result = seed_implement_from_decompose(tmp_path, rel)

    assert result["ok"] is True
    assert (
        result["path"]
        == "memory-bank/back/implement/implement-T-004-tg-async-rps/"
        "s01-llm-async.yaml"
    )
    assert (tmp_path / result["path"]).is_file()
    assert not (
        tmp_path / "memory-bank/back/implement/implement-T-004/s01-llm-async.yaml"
    ).exists()


def test_seed_reuses_existing_plan_id_hub(tmp_path: Path) -> None:
    _hooks()
    from epic_yaml import seed_implement_from_decompose

    rel = (
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/"
        "s03-gg-interprocess-lock.yaml"
    )
    _write(tmp_path, rel, _decompose_doc(step_id="s03"))
    existing = (
        "memory-bank/back/implement/implement-T-004/"
        "s03-gg-interprocess-lock.yaml"
    )
    _write(tmp_path, existing, _implement_doc())

    result = seed_implement_from_decompose(tmp_path, rel)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["path"] == existing


def test_resolve_implement_path_falls_back_to_plan_id_hub(tmp_path: Path) -> None:
    _hooks()
    from epic_yaml import resolve_implement_path

    rel = (
        "memory-bank/back/implement/implement-T-004/"
        "s03-gg-interprocess-lock.yaml"
    )
    _write(tmp_path, rel, _implement_doc())

    found = resolve_implement_path(
        tmp_path,
        "back",
        "T-004-tg-async-rps",
        "s03",
        plan_id="T-004",
    )

    assert found == rel


def test_mark_index_refuses_completed_when_implement_in_progress(
    tmp_path: Path,
) -> None:
    _hooks()
    import epic.core as epic_core

    _index_pair(tmp_path, status="pending")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-T-004/"
        "s03-gg-interprocess-lock.yaml",
        _implement_doc(status="in_progress"),
    )

    result = epic_core.mark_index_step_status(
        tmp_path,
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.md",
        "s03",
        "completed",
    )

    assert result["ok"] is False
    assert result.get("diagnostic") == "index_implement_conflict"
    yaml_text = (
        tmp_path
        / "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.yaml"
    ).read_text(encoding="utf-8")
    assert "status: pending" in yaml_text
    assert "status: completed" not in yaml_text


def test_seed_implement_rejects_decompose_outside_cwd(tmp_path: Path) -> None:
    _hooks()
    from epic_yaml import seed_implement_from_decompose

    product = tmp_path / "product"
    other = tmp_path / "other"
    product.mkdir()
    other.mkdir()
    rel = "memory-bank/back/plan/decompose-T-004-tg-async-rps/s01-llm-async.yaml"
    dec_path = _write(other, rel, _decompose_doc())
    abs_dec = str(dec_path.resolve())

    result = seed_implement_from_decompose(product, abs_dec)

    assert result["ok"] is False
    assert "outside --cwd" in result["error"]
    assert not (product / "memory-bank/back/implement").exists()


def test_seed_implement_rejects_hub_epic_in_product_cwd(tmp_path: Path) -> None:
    _hooks()
    from epic_yaml import seed_implement_from_decompose

    rel = (
        "memory-bank/back/plan/decompose-T-HUB-002-canon-sync/"
        "s05-graphify-hub-na-integ-plan.yaml"
    )
    _write(
        tmp_path,
        rel,
        _decompose_doc(step_id="s05", plan_id="T-HUB-002"),
    )

    result = seed_implement_from_decompose(tmp_path, rel)

    assert result["ok"] is False
    assert "anti-mix" in result["error"]
    assert "T-HUB" in result["error"]
    assert not (
        tmp_path
        / "memory-bank/back/implement/implement-T-HUB-002-canon-sync/s05-graphify-hub-na-integ-plan.yaml"
    ).exists()


def test_validate_index_accepts_completed_implement_on_plan_id_hub(
    tmp_path: Path,
) -> None:
    _hooks()
    import epic.core as epic_core

    _index_pair(tmp_path, status="completed")
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-T-004/"
        "s03-gg-interprocess-lock.yaml",
        _implement_doc(status="completed"),
    )

    errors = epic_core.validate_index_vs_implement(
        tmp_path,
        "memory-bank/back/plan/decompose-T-004-tg-async-rps/index.md",
    )

    assert errors == []
