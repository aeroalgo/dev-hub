"""Episode packages retention and cleanup module."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from loop.episodes.core import episodes_root
from loop.schemas.episode import EpisodeManifest

logger = logging.getLogger(__name__)

EPIC_EPISODE_RETENTION_DAYS_DEFAULT = 30


def _parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parse ISO datetime string into UTC datetime object."""
    if not dt_str:
        return None
    try:
        # Replace Z with +00:00 for datetime.fromisoformat compatibility
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def prune_episodes(cwd: str | Path, days: int | None = None) -> int:
    """Prune episode package directories older than specified retention days.

    If `days` is None, reads EPIC_EPISODE_RETENTION_DAYS env var (default 30).
    Returns total number of pruned episode directories.
    """
    if days is None:
        env_val = os.environ.get("EPIC_EPISODE_RETENTION_DAYS")
        if env_val:
            try:
                days = int(env_val)
            except ValueError:
                days = EPIC_EPISODE_RETENTION_DAYS_DEFAULT
        else:
            days = EPIC_EPISODE_RETENTION_DAYS_DEFAULT

    root = episodes_root(cwd)
    if not root.exists():
        return 0

    now = datetime.now(timezone.utc)
    pruned_count = 0

    for ep_dir in root.iterdir():
        if not ep_dir.is_dir():
            continue

        manifest_file = ep_dir / "manifest.json"
        if not manifest_file.exists():
            continue

        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            manifest = EpisodeManifest.model_validate(data)
        except Exception:
            logger.warning("Failed to parse manifest in %s during prune", ep_dir)
            continue

        timestamp_str = manifest.ended_at or manifest.started_at
        dt = _parse_iso_datetime(timestamp_str)
        if dt is None:
            continue

        age_days = (now - dt).total_seconds() / 86400.0
        if age_days > days:
            try:
                shutil.rmtree(ep_dir)
                pruned_count += 1
                logger.info("Pruned old episode directory %s (age: %.1f days)", ep_dir.name, age_days)
            except Exception as e:
                logger.error("Failed to remove episode dir %s: %s", ep_dir, e)

    return pruned_count
