from __future__ import annotations

from pathlib import Path
from typing import Any

from loop.board_projection.docs_publish import publish_board_docs
from loop.board_projection.mapping import BoardEpicMap, EpicMapEntry, save_board_epic_map
from loop.board_projection.protocol import BoardProjectionAdapter, EpicRef
from loop.kernel.cli import main


PROMPT = """## Epic

### Outcome
Зеркало эпика на доске.

---

## Board

title: docs publish title

summary: Краткое описание для доски.
"""


class CapturingAttachAdapter(BoardProjectionAdapter):
    def __init__(self) -> None:
        self.attached: list[tuple[str, str, bytes]] = []

    @property
    def provider_name(self) -> str:
        return "bitrix24"

    def ensure_card(self, epic: EpicRef) -> str:
        return "1"

    def move_card(self, external_id: str, phase: str) -> None:
        return None

    def attach_document(self, external_id: str, filename: str, content: bytes) -> dict[str, Any]:
        self.attached.append((external_id, filename, content))
        return {"provider": "bitrix24", "external_id": external_id, "filename": filename, "attachment_id": 1}


def _seed(tmp_path: Path) -> Path:
    epic = "E-DOCS"
    md = tmp_path / f"memory-bank/back/plan/{epic}/md"
    md.mkdir(parents=True)
    (md / "prompt.md").write_text(PROMPT, encoding="utf-8")
    (md / "plan.md").write_text("# Plan\n\nbody\n", encoding="utf-8")
    cfg = tmp_path / ".loop/board-projection.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        """
schema: loop-board-projection/v1
provider: bitrix24
role_allowlist: [back]
phase_alias:
  DONE: done
providers:
  bitrix24:
    webhook_url: https://example.test/rest/1/x/
    group_id: 26
    responsible_id: 274
    stage_map: {done: "1"}
  plane:
    base_url: https://example.test
    api_key: k
    workspace_slug: w
    project_id: p
    state_map: {done: "s"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    save_board_epic_map(
        BoardEpicMap(
            provider="bitrix24",
            epics={epic: EpicMapEntry(external_id="34861", last_phase="DONE")},
        ),
        tmp_path / ".loop/board-epic-map.yaml",
    )
    return tmp_path


def test_publish_board_docs_attaches_prompt_and_plan(tmp_path: Path):
    _seed(tmp_path)
    adapter = CapturingAttachAdapter()
    result = publish_board_docs(
        project_root=tmp_path,
        epic_id="E-DOCS",
        role="back",
        adapter=adapter,
    )
    assert result.status == "success"
    assert len(adapter.attached) == 2
    names = [item[1] for item in adapter.attached]
    assert names == ["E-DOCS-prompt.md", "E-DOCS-plan.md"]
    assert b"## Epic" in adapter.attached[0][2]
    assert b"# Plan" in adapter.attached[1][2]


def test_publish_board_docs_requires_mapping(tmp_path: Path):
    _seed(tmp_path)
    save_board_epic_map(BoardEpicMap(provider="bitrix24", epics={}), tmp_path / ".loop/board-epic-map.yaml")
    result = publish_board_docs(
        project_root=tmp_path,
        epic_id="E-DOCS",
        role="back",
        adapter=CapturingAttachAdapter(),
    )
    assert result.status == "error"
    assert "board card missing" in (result.error or "")


def test_cli_board_docs(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    adapter = CapturingAttachAdapter()
    monkeypatch.setattr("loop.board_projection.docs_publish.get_adapter", lambda _cfg: adapter)
    rc = main(
        [
            "board-docs",
            "--project",
            str(tmp_path),
            "--epic",
            "E-DOCS",
            "--role",
            "back",
            "--json",
        ]
    )
    assert rc == 0
    assert len(adapter.attached) == 2
