"""Detector for orphan events directories and episode retention policy enforcement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from loop.janitor.schema import JanitorFinding
from loop.schemas.episode import EpisodeManifest


def detect_orphan_events_dir(cwd: Path) -> list[JanitorFinding]:
    """Scan runtime/events/ (or events/ under runtime or cwd) for directories without matching episode manifest."""
    findings: list[JanitorFinding] = []

    # Check potential events root directories
    candidate_roots = [
        cwd / "runtime" / "events",
        cwd / "events",
    ]
    # Also check runtime/*/events/ if any
    runtime_dir = cwd / "runtime"
    if runtime_dir.is_dir():
        for item in runtime_dir.iterdir():
            if item.is_dir() and item.name != "events":
                candidate_roots.append(item / "events")

    # Collect existing episode manifests / episode IDs
    existing_episode_ids: set[str] = set()
    candidate_episodes_roots = [
        cwd / "runtime" / "episodes",
        cwd / "episodes",
    ]
    if runtime_dir.is_dir():
        for item in runtime_dir.iterdir():
            if item.is_dir() and item.name != "episodes":
                candidate_episodes_roots.append(item / "episodes")

    for ep_root in candidate_episodes_roots:
        if ep_root.is_dir():
            for ep_dir in ep_root.iterdir():
                if ep_dir.is_dir():
                    existing_episode_ids.add(ep_dir.name)
                    manifest_file = ep_dir / "manifest.json"
                    if manifest_file.is_file():
                        try:
                            data = json.loads(manifest_file.read_text(encoding="utf-8"))
                            if isinstance(data, dict) and data.get("episode_id"):
                                existing_episode_ids.add(str(data["episode_id"]))
                        except Exception:
                            pass

    processed_events_dirs: set[Path] = set()
    for events_root in candidate_roots:
        if not events_root.is_dir():
            continue
        for ev_dir in events_root.iterdir():
            if not ev_dir.is_dir() or ev_dir in processed_events_dirs:
                continue
            processed_events_dirs.add(ev_dir)

            # A directory in events/ is an orphan if ev_dir.name is not in existing_episode_ids
            # and no episode manifest anywhere references this events dir.
            if ev_dir.name not in existing_episode_ids:
                rel_path = ev_dir.relative_to(cwd) if ev_dir.is_relative_to(cwd) else ev_dir
                findings.append(
                    JanitorFinding(
                        category="orphan_events_dir",
                        description=f"Events directory '{ev_dir.name}' has no matching episode manifest",
                        target_path=str(rel_path),
                        actionable=True,
                        metadata={
                            "events_dir": str(rel_path),
                            "dir_name": ev_dir.name,
                        },
                    )
                )

    return findings


def detect_episode_retention_exceeded(
    cwd: Path, max_age_days: int = 30
) -> list[JanitorFinding]:
    """Scan runtime/episodes/ (or episodes/ under runtime or cwd) for episodes older than retention threshold."""
    findings: list[JanitorFinding] = []

    candidate_episodes_roots = [
        cwd / "runtime" / "episodes",
        cwd / "episodes",
    ]
    runtime_dir = cwd / "runtime"
    if runtime_dir.is_dir():
        for item in runtime_dir.iterdir():
            if item.is_dir() and item.name != "episodes":
                candidate_episodes_roots.append(item / "episodes")

    now_utc = datetime.now(timezone.utc)
    processed_ep_dirs: set[Path] = set()

    for ep_root in candidate_episodes_roots:
        if not ep_root.is_dir():
            continue
        for ep_dir in ep_root.iterdir():
            if not ep_dir.is_dir() or ep_dir in processed_ep_dirs:
                continue
            processed_ep_dirs.add(ep_dir)

            manifest_file = ep_dir / "manifest.json"
            created_at: datetime | None = None
            episode_id = ep_dir.name

            if manifest_file.is_file():
                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    manifest = EpisodeManifest.model_validate(data)
                    episode_id = manifest.episode_id
                    if manifest.started_at:
                        created_at = datetime.fromisoformat(manifest.started_at)
                except Exception:
                    pass

            if created_at is None:
                # Fallback to dir mtime
                try:
                    mtime = ep_dir.stat().st_mtime
                    created_at = datetime.fromtimestamp(mtime, tz=timezone.utc)
                except Exception:
                    continue

            # Ensure created_at has timezone
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_days = (now_utc - created_at).total_seconds() / 86400.0
            if age_days > max_age_days:
                rel_path = ep_dir.relative_to(cwd) if ep_dir.is_relative_to(cwd) else ep_dir
                findings.append(
                    JanitorFinding(
                        category="episode_retention_exceeded",
                        description=f"Episode '{episode_id}' age ({age_days:.1f} days) exceeds retention window ({max_age_days} days)",
                        target_path=str(rel_path),
                        actionable=True,
                        metadata={
                            "episode_id": episode_id,
                            "episode_dir": str(rel_path),
                            "age_days": round(age_days, 1),
                            "max_age_days": max_age_days,
                        },
                    )
                )

    return findings
