from __future__ import annotations

from pathlib import Path

from loop.board_projection.card_copy import (
    format_card_description,
    parse_board_card_copy,
    parse_outcome_fallback,
    resolve_card_fields,
)
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.board_projection.service import project_epic_phase


PROMPT_WITH_BOARD = """## Epic

### Outcome
Полный outcome для агента, длиннее board summary.

### In
- work

---

## Covering

n/a — single epic

---

## Board

title: проекция эпиков на доску

summary: После finish карточка появляется или двигается.
Loop — SoT, доска — зеркало.
"""


PROMPT_OUTCOME_ONLY = """## Epic

### Outcome
Карточка эпика зеркалится на внешнюю доску после перехода фазы.

### In
- work
"""


class CapturingAdapter(BoardProjectionAdapter):
    def __init__(self) -> None:
        self.created: list[EpicRef] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    def ensure_card(self, epic: EpicRef) -> str:
        self.created.append(epic)
        return "42"

    def move_card(self, external_id: str, phase: str) -> None:
        return None

    def validate_mappings(self) -> None:
        return None


def test_parse_board_card_copy_reads_title_and_multiline_summary():
    copy = parse_board_card_copy(PROMPT_WITH_BOARD)
    assert copy is not None
    assert copy.title == "проекция эпиков на доску"
    assert "После finish" in copy.summary
    assert "зеркало" in copy.summary


def test_parse_outcome_fallback_when_board_missing():
    copy = parse_outcome_fallback(PROMPT_OUTCOME_ONLY)
    assert copy is not None
    assert "зеркалится" in copy.summary
    assert copy.title.startswith("Карточка эпика")


def test_format_card_description_adds_epic_and_plan_path():
    text = format_card_description(
        epic_id="E1",
        summary="Кратко",
        role="back",
        kind="feature",
    )
    assert "Кратко" in text
    assert "Epic: E1" in text
    assert "memory-bank/back/plan/E1/md/plan.md" in text


def test_resolve_card_fields_from_prompt_board(tmp_path: Path):
    prompt = tmp_path / "memory-bank/back/plan/E1/md/prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text(PROMPT_WITH_BOARD, encoding="utf-8")
    (tmp_path / "memory-bank/back/plan/E1/md/plan.md").write_text("# plan\n", encoding="utf-8")

    title, description = resolve_card_fields(tmp_path, "E1", role="back")
    assert title == "проекция эпиков на доску"
    assert "После finish" in description
    assert "memory-bank/back/plan/E1/md/plan.md" in description


def test_resolve_card_fields_from_bugfix_prompt_without_plan(tmp_path: Path):
    prompt = tmp_path / "memory-bank/back/bugfix/bugfix-demo/prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text(
        "## Board\n\ntitle: Bugfix: демо\nsummary: |\n  Закрытый баг без plan/.\n",
        encoding="utf-8",
    )

    title, description = resolve_card_fields(tmp_path, "bugfix-demo", role="back")
    assert title == "Bugfix: демо"
    assert "без plan/" in description
    assert "memory-bank/back/bugfix/bugfix-demo/prompt.md" in description
    assert "/plan/" not in description


def test_project_epic_phase_create_uses_board_copy(tmp_path: Path):
    prompt = tmp_path / "memory-bank/back/plan/E1/md/prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text(PROMPT_WITH_BOARD, encoding="utf-8")
    (tmp_path / "memory-bank/back/plan/E1/md/plan.md").write_text("# plan\n", encoding="utf-8")

    cfg = tmp_path / ".loop/board-projection.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        """
schema: loop-board-projection/v1
provider: plane
role_allowlist: [back]
phase_alias:
  PLAN: design
  DECOMPOSE: design
providers:
  bitrix24:
    webhook_url: https://example.test/rest/1/x/
    group_id: 1
    responsible_id: 1
    stage_map: {design: "10"}
  plane:
    base_url: https://example.test
    api_key: k
    workspace_slug: w
    project_id: p
    state_map: {design: "s"}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    adapter = CapturingAdapter()

    result = project_epic_phase(
        project_root=tmp_path,
        epic_id="E1",
        phase="DECOMPOSE",
        role="back",
        config_path=cfg,
        map_path=tmp_path / ".loop/board-epic-map.yaml",
        adapter=adapter,
    )
    assert result.status == "success"
    assert len(adapter.created) == 1
    card = adapter.created[0]
    assert card.title == "проекция эпиков на доску"
    assert "Loop — SoT" in card.description or "зеркало" in card.description
    assert card.phase == "DECOMPOSE"
