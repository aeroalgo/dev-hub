#!/usr/bin/env python3
"""SessionStart — inject epic initialUserMessage (fresh -p session)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import emit, product_cwd, read_stdin  # noqa: E402
from epic_lib import session_start_payload  # noqa: E402


def auto_scaffold_if_needed(cwd: str | Path) -> None:
    """Auto-scaffold decompose on phase enter when tree is missing (FR-016)."""
    cwd_p = Path(cwd).resolve()
    try:
        from epic import load_epic_state
        from loop.paths.epic_layout import resolve, EpicLayoutKind
    except ImportError:
        return

    st = load_epic_state(cwd_p)
    if not st:
        return

    epic_id = str(st.get("armed_epic") or "").strip()
    role = str(st.get("role") or "back").strip().lower()
    armed_step = str(st.get("armed_step") or st.get("phase") or "").strip().upper()

    if not epic_id:
        return

    if armed_step == "DECOMPOSE":
        yaml_idx = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=cwd_p)
        md_idx = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=cwd_p)
        if not yaml_idx.is_file() and not md_idx.is_file():
            plan_yaml = resolve(role, epic_id, EpicLayoutKind.PLAN_YAML, project_root=cwd_p)
            if plan_yaml.is_file():
                from loop.mb_scaffold.scaffold_decompose import scaffold_decompose
                scaffold_decompose(epic_id=epic_id, role=role, project_root=cwd_p)


def _check_preflight_drift(cwd: str) -> None:
    if os.environ.get("EPIC_RUNTIME") != "codex":
        return
    bin_sync = Path(cwd) / "bin" / "runtime-sync"
    if not bin_sync.exists():
        bin_sync = Path(__file__).resolve().parents[2] / "bin" / "runtime-sync"
    manifest_path = Path(cwd) / "harness" / "manifest.yaml"
    if not bin_sync.exists() or not manifest_path.exists():
        return
    try:
        res = subprocess.run(
            [sys.executable, str(bin_sync), "--manifest", str(manifest_path), "--runtime", "codex", "--check"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            sys.stderr.write("WARNING: Runtime drift detected for codex runtime. Run `bin/runtime-sync --apply` to resolve.\n")
    except Exception:
        pass


def main() -> None:
    data = read_stdin()
    cwd = str(product_cwd(data.get("cwd") or ""))
    source = data.get("source") or data.get("session_source") or ""

    _check_preflight_drift(cwd)
    auto_scaffold_if_needed(cwd)

    payload = session_start_payload(cwd, source)
    if not payload:
        return
    out: dict = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            **payload,
        }
    }
    emit(out)


if __name__ == "__main__":
    main()
