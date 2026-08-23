#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import _wf


def main() -> None:
    payload = json.load(sys.stdin)
    root = _wf.workspace_root(payload)
    fp = payload.get("file_path") or ""
    if not fp or _wf.should_skip_track(fp):
        return
    try:
        rel = str(Path(fp).resolve().relative_to(root))
    except ValueError:
        rel = fp
    art = _wf.artifacts_dir(root)
    lst = art / "session-edits.list"
    seen = set()
    if lst.is_file():
        seen = {line.strip() for line in lst.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()}
    if rel not in seen:
        seen.add(rel)
        lst.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
