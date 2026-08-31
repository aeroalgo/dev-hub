"""CLI subcommand functions for inspecting episode packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loop.episodes.core import episode_dir, list_episodes
from loop.schemas.episode import EpisodeManifest


def scan_episodes(cwd: str | Path) -> list[EpisodeManifest]:
    """Scan all valid episodes in cwd sorted by episode_id descending."""
    manifests: list[EpisodeManifest] = []
    ep_ids = list_episodes(cwd)
    for ep_id in ep_ids:
        ep_path = episode_dir(cwd, ep_id)
        manifest_file = ep_path / "manifest.json"
        if manifest_file.exists():
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                manifests.append(EpisodeManifest.model_validate(data))
            except Exception:
                continue
    manifests.sort(key=lambda m: m.episode_id, reverse=True)
    return manifests


def format_episode_list(manifests: list[EpisodeManifest]) -> str:
    """Format episode manifests into stdout summary table/lines."""
    if not manifests:
        return "No episodes found."

    headers = ["EPISODE_ID", "STARTED_AT", "DECIDE", "ARMED_STEP", "HALT_REASON"]
    rows = []
    for m in manifests:
        rows.append([
            m.episode_id,
            m.started_at or "-",
            m.decide or "-",
            m.armed_step or "-",
            m.halt_reason or "-",
        ])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    lines = [fmt.format(*headers)]
    for row in rows:
        lines.append(fmt.format(*row))
    return "\n".join(lines)


def episode_list(cwd: str | Path, last: int | None = None) -> list[dict[str, Any]]:
    """Scan and return episode manifests dicts up to `last` count."""
    manifests = scan_episodes(cwd)
    if last is not None and last > 0:
        manifests = manifests[:last]
    return [m.model_dump(mode="json") for m in manifests]


def show_episode(cwd: str | Path, episode_id: str) -> dict[str, Any]:
    """Return detailed manifest dict + artifact files list for a single episode."""
    ep_path = episode_dir(cwd, episode_id)
    manifest_file = ep_path / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Episode manifest not found for episode_id: {episode_id}")

    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest = EpisodeManifest.model_validate(data)

    artifacts: list[str] = []
    art_dir = ep_path / "artifacts"
    if art_dir.exists():
        for p in sorted(art_dir.rglob("*")):
            if p.is_file():
                artifacts.append(p.relative_to(art_dir).as_posix())

    result = manifest.model_dump(mode="json")
    result["artifacts_bundle"] = artifacts
    return result
