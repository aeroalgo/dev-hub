"""Episode packages module core functions."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic_paths import epic_dir as get_epic_dir  # noqa: E402
from loop.episodes.bundle import compute_load_now_sha256, copy_artifacts  # noqa: E402
from loop.schemas.episode import EpisodeManifest  # noqa: E402

_UTC_COMPACT_RE = re.compile(r"^\d{8}_\d{6}$")


def episodes_root(cwd: str | Path) -> Path:
    """Return Path to runtime/<slug>/episodes/ directory."""
    cwd_p = Path(cwd).expanduser().resolve()
    base_epic_dir = get_epic_dir(cwd_p)
    return base_epic_dir.parent / "episodes"


def episode_dir(cwd: str | Path, episode_id: str) -> Path:
    """Return Path to runtime/<slug>/episodes/<episode_id>/ directory."""
    return episodes_root(cwd) / episode_id


def list_episodes(cwd: str | Path) -> list[str]:
    """List episode directory names under runtime/<slug>/episodes/."""
    ep_root = episodes_root(cwd)
    if not ep_root.exists():
        return []
    return [
        d.name
        for d in ep_root.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    ]


def begin_episode(
    cwd: str | Path,
    *,
    epic_id: str = "T-HUB-031",
    role: str = "back",
    armed_step: str = "s01",
) -> str:
    """Create episode directory with manifest-stub.json and return episode_id string."""
    now = datetime.now(timezone.utc)
    utc_compact = now.strftime("%Y%m%d_%H%M%S")
    epic_id_short = epic_id.replace("-", "").lower()
    random_hex = os.urandom(2).hex()
    ep_id = f"{utc_compact}_{epic_id_short}_{random_hex}"

    target_dir = episode_dir(cwd, ep_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stub_manifest = EpisodeManifest(
        episode_id=ep_id,
        started_at=now.isoformat(),
        epic_id=epic_id,
        role=role,
        armed_step=armed_step,
    )

    stub_file = target_dir / "manifest-stub.json"
    stub_file.write_text(
        json.dumps(stub_manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return ep_id


def finalize_episode(
    cwd: str | Path,
    episode_id: str,
    check_after_result: dict[str, Any] | None = None,
) -> EpisodeManifest:
    """Write valid manifest.json atomically to episode directory and return EpisodeManifest."""
    target_dir = episode_dir(cwd, episode_id)
    stub_file = target_dir / "manifest-stub.json"

    initial_data: dict[str, Any] = {}
    if stub_file.is_file():
        try:
            initial_data = json.loads(stub_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    initial_data["ended_at"] = now.isoformat()

    if check_after_result:
        for k in (
            "sNN",
            "prompt_hash",
            "fingerprint_before",
            "fingerprint_after",
            "decide",
            "halt_reason",
            "incident_ids",
            "event_seq_range",
            "load_now_paths",
            "load_now_sha256",
        ):
            if k in check_after_result:
                initial_data[k] = check_after_result[k]

        if "load_now_paths" in check_after_result and not check_after_result.get("load_now_sha256"):
            paths = check_after_result.get("load_now_paths") or []
            if isinstance(paths, list):
                initial_data["load_now_sha256"] = compute_load_now_sha256(cwd, paths)

    art_refs = copy_artifacts(cwd, target_dir, check_after_result)
    initial_data["artifact_refs"] = art_refs

    manifest = EpisodeManifest.model_validate(initial_data)

    tmp_file = target_dir / "manifest.json.tmp"
    final_file = target_dir / "manifest.json"

    tmp_file.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp_file.replace(final_file)

    return manifest
