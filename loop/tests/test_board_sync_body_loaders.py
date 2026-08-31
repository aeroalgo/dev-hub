from __future__ import annotations

from pathlib import Path
import yaml

from loop.board_sync.body_loaders import load_gate_body, load_step_body


def test_load_gate_body_happy_path(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# [T-HUB-019] Plan Title\n\n"
        "## Цель\n"
        "Achieve sync enrichment.\n\n"
        "## Контекст\n"
        "First paragraph of context.\n\n"
        "Second paragraph of context.\n\n"
        "## User Stories\n"
        "| ID | Description |\n"
        "|---|---|\n"
        "| US1 | Story 1 |\n"
        "| US2 | Story 2 |\n"
        "| US3 | Story 3 |\n"
        "| US4 | Story 4 |\n"
        "| US5 | Story 5 |\n"
        "| US6 | Story 6 |\n",
        encoding="utf-8",
    )

    body = load_gate_body(plan, "reason_fallback")
    assert body is not None
    assert "# [T-HUB-019] Plan Title" in body
    assert "## Цель\nAchieve sync enrichment." in body
    assert "First paragraph of context." in body
    assert "Second paragraph of context." not in body
    assert "| US5 | Story 5 |" in body
    assert "| US6 | Story 6 |" not in body


def test_load_gate_body_missing_plan_reason_code(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"
    assert load_gate_body(missing, "analyze_required") == "analyze_required"
    assert load_gate_body(None, "plan_missing") == "plan_missing"
    assert load_gate_body(None, None) is None



def test_load_step_body_happy_path(tmp_path: Path) -> None:
    shard = tmp_path / "s01.yaml"
    shard.write_text(
        yaml.safe_dump(
            {
                "goal": "Do the thing",
                "delta": ["ADD feature A", "EDIT file B"],
                "files": ["path/a.py", "path/b.py"],
            }
        ),
        encoding="utf-8",
    )

    body, diag = load_step_body(shard)
    assert diag is None
    assert body is not None
    assert "Do the thing" in body
    assert "Delta:\n- ADD feature A\n- EDIT file B" in body
    assert "Files / Context:\n- `path/a.py`\n- `path/b.py`" in body


def test_load_step_body_fallback_title_consumes(tmp_path: Path) -> None:
    shard = tmp_path / "s02.yaml"
    shard.write_text(
        yaml.safe_dump(
            {
                "title": "Title fallback",
                "context": {
                    "consumes": ["c1", "c2", "c3", "c4"],
                },
            }
        ),
        encoding="utf-8",
    )

    body, diag = load_step_body(shard)
    assert diag is None
    assert body is not None
    assert "Title fallback" in body
    assert "`c1`" in body
    assert "`c2`" in body
    assert "`c3`" in body
    assert "`c4`" not in body


def test_load_step_body_truncation_4000(tmp_path: Path) -> None:
    shard = tmp_path / "s03.yaml"
    long_goal = "x" * 5000
    shard.write_text(yaml.safe_dump({"goal": long_goal}), encoding="utf-8")

    body, diag = load_step_body(shard)
    assert diag is None
    assert body is not None
    assert len(body) == 4000
    assert body.endswith("…")


def test_load_step_body_missing(tmp_path: Path) -> None:
    shard = tmp_path / "missing.yaml"
    body, diag = load_step_body(shard)
    assert body is None
    assert diag is not None
    assert "not found" in diag


def test_load_step_body_broken_yaml(tmp_path: Path) -> None:
    shard = tmp_path / "broken.yaml"
    shard.write_text("invalid: yaml: [", encoding="utf-8")

    body, diag = load_step_body(shard)
    assert body is None
    assert diag is not None
    assert "Failed to read shard" in diag
