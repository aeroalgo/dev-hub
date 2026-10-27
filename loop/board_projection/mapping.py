from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

DEFAULT_MAP_PATH = Path(".loop/board-epic-map.yaml")


class EpicMapEntry(BaseModel):
    external_id: str | None = Field(default=None, description="External card/issue ID on the board")
    last_phase: str | None = Field(default=None, description="Last projected loop phase")
    sync_error: str | None = Field(default=None, description="Last synchronization error if failed")
    updated_at: str | None = Field(default=None, description="ISO timestamp of last update")


class BoardEpicMap(BaseModel):
    schema_version: str = Field(default="loop-board-epic-map/v1", alias="schema")
    provider: str = Field(default="", description="Active board projection provider name")
    epics: dict[str, EpicMapEntry] = Field(default_factory=dict, description="Map of epic_id -> EpicMapEntry")


def resolve_map_path(
    project_root: Path | str | None = None,
    explicit_path: Path | str | None = None,
) -> Path:
    if explicit_path is not None:
        return Path(explicit_path)
    root = Path(project_root) if project_root is not None else Path.cwd()
    return root / DEFAULT_MAP_PATH


def load_board_epic_map(map_path: Path | str) -> BoardEpicMap:
    """
    Load BoardEpicMap from YAML file.
    If file does not exist, returns empty BoardEpicMap.
    """
    path = Path(map_path)
    if not path.exists() or not path.is_file():
        return BoardEpicMap(provider="", epics={})

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text) or {}
    except Exception:
        return BoardEpicMap(provider="", epics={})

    if not isinstance(data, dict):
        return BoardEpicMap(provider="", epics={})

    try:
        return BoardEpicMap.model_validate(data)
    except Exception:
        return BoardEpicMap(provider="", epics={})


def save_board_epic_map(board_map: BoardEpicMap, map_path: Path | str) -> None:
    """
    Atomically save BoardEpicMap to YAML file.
    """
    path = Path(map_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = board_map.model_dump(by_alias=True)
    yaml_content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    # Atomic write via temporary file in the same directory
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            delete=False,
            prefix=".board-epic-map-",
            suffix=".tmp",
        ) as tmp:
            temp_file = Path(tmp.name)
            tmp.write(yaml_content)
            tmp.flush()
            os.fsync(tmp.fileno())

        temp_file.replace(path)
    finally:
        if temp_file is not None and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
