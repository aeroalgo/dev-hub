"""Episode artifact bundling utilities."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from epic_paths import epic_dir as get_epic_dir  # noqa: E402
from loop.incidents.trace import read_session_trace_tail  # noqa: E402


def compute_file_sha256(path: Path | str) -> str:
    """Compute sha256 hex digest for a file."""
    p = Path(path)
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_load_now_sha256(cwd: str | Path, paths: list[str]) -> list[str]:
    """Compute sha256 hex digest for each path in paths list."""
    cwd_p = Path(cwd).expanduser().resolve()
    sha_list: list[str] = []
    for p_str in paths:
        p = Path(p_str)
        if not p.is_absolute():
            p = cwd_p / p
        sha_list.append(compute_file_sha256(p))
    return sha_list


def copy_artifacts(
    cwd: str | Path,
    episode_dir: Path | str,
    check_after_result: dict[str, Any] | None = None,
    *,
    trace_lines: int = 50,
) -> dict[str, str]:
    """Copy session artifacts into episode directory.

    Returns dict mapping artifact name -> relative path inside episode_dir.
    Copy errors are handled gracefully without raising.
    """
    ep_dir = Path(episode_dir)
    ep_dir.mkdir(parents=True, exist_ok=True)
    base_epic_dir = get_epic_dir(cwd)
    artifact_refs: dict[str, str] = {}

    # 1. check_after.json
    if check_after_result is not None:
        try:
            ca_data = dict(check_after_result)
            inc_prompt = os.getenv("EPIC_EPISODE_INCLUDE_PROMPT", "0").strip().lower()
            if inc_prompt not in ("1", "true", "yes"):
                ca_data.pop("prompt", None)
                ca_data.pop("raw_prompt", None)
                ca_data.pop("user_prompt", None)

            ca_file = ep_dir / "check_after.json"
            ca_file.write_text(
                json.dumps(ca_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            artifact_refs["check_after"] = "check_after.json"
        except Exception:
            pass

    # 2. checkpoint_snapshot.json
    try:
        cp_src = base_epic_dir / "checkpoint.json"
        if not cp_src.is_file():
            cp_src = base_epic_dir / "checkpoint_snapshot.json"
        if cp_src.is_file():
            cp_dst = ep_dir / "checkpoint_snapshot.json"
            shutil.copy2(cp_src, cp_dst)
            artifact_refs["checkpoint_snapshot"] = "checkpoint_snapshot.json"
    except Exception:
        pass

    # 3. gate_verdict.json
    try:
        gv_src = None
        gates_dir = base_epic_dir / "gates"
        if gates_dir.is_dir():
            gv_files = sorted(gates_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if gv_files:
                gv_src = gv_files[0]
        if not gv_src:
            candidate = base_epic_dir / "gate_verdict.json"
            if candidate.is_file():
                gv_src = candidate

        if gv_src and gv_src.is_file():
            gv_dst = ep_dir / "gate_verdict.json"
            shutil.copy2(gv_src, gv_dst)
            artifact_refs["gate_verdict"] = "gate_verdict.json"
    except Exception:
        pass

    # 4. trace_tail.jsonl
    try:
        tail_entries = read_session_trace_tail(base_epic_dir, limit=trace_lines)
        if tail_entries:
            tt_file = ep_dir / "trace_tail.jsonl"
            lines = [json.dumps(entry, ensure_ascii=False) for entry in tail_entries]
            tt_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            artifact_refs["trace_tail"] = "trace_tail.jsonl"
    except Exception:
        pass

    return artifact_refs
