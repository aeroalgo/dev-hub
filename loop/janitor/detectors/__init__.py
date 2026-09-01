"""Janitor entropy detectors package."""

from __future__ import annotations

from typing import Callable
from pathlib import Path
from loop.janitor.schema import JanitorFinding

from loop.janitor.detectors.orphan import detect_orphan_implement_yaml
from loop.janitor.detectors.stale_index import detect_stale_index_status
from loop.janitor.detectors.dead_ref import detect_dead_plan_ref
from loop.janitor.detectors.duplicate_epic import detect_duplicate_epic_id
from loop.janitor.detectors.events_retention import (
    detect_orphan_events_dir,
    detect_episode_retention_exceeded,
)

DETECTORS: list[Callable[[Path], list[JanitorFinding]]] = [
    detect_orphan_implement_yaml,
    detect_stale_index_status,
    detect_dead_plan_ref,
    detect_duplicate_epic_id,
    detect_orphan_events_dir,
    detect_episode_retention_exceeded,
]

__all__ = [
    "DETECTORS",
    "detect_orphan_implement_yaml",
    "detect_stale_index_status",
    "detect_dead_plan_ref",
    "detect_duplicate_epic_id",
    "detect_orphan_events_dir",
    "detect_episode_retention_exceeded",
]
