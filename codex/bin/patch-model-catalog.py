#!/usr/bin/env python3
"""Inject ~/.claude/extra-models.json entries into the Codex CLI / VS Code
extension model picker.

Codex ships an official extension point for this: `model_catalog_json` in
`~/.codex/config.toml` points at a JSON file with a `models` array that
*replaces* the built-in catalog. So instead of patching minified webview JS
(fragile, breaks on every extension update, like the Claude Code approach),
we ask the installed `codex` binary for its own bundled catalog
(`codex debug models --bundled`), clone one entry as a template for every
row in extra-models.json, and write the merged result back out.

Idempotent: safe to re-run any time (e.g. after `npm i -g @openai/codex`
upgrades, or after editing extra-models.json).

Usage:
  python3 ~/.claude/../PyProject/dev-hub/codex/bin/patch-model-catalog.py [apply|status]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
EXTRA_PATH = HOME / ".claude" / "extra-models.json"
CODEX_HOME = Path(__import__("os").environ.get("CODEX_HOME", str(HOME / ".codex")))
CATALOG_PATH = CODEX_HOME / "model-catalog.json"
CONFIG_PATH = CODEX_HOME / "config.toml"
TEMPLATE_SLUG = "gpt-5.6-luna"  # smallest/fastest bundled model; cloned per extra entry


def load_extra() -> list[dict]:
    if not EXTRA_PATH.exists():
        raise SystemExit(f"missing {EXTRA_PATH}")
    rows = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"{EXTRA_PATH} must contain a JSON array")
    return rows


def load_bundled() -> list[dict]:
    proc = subprocess.run(
        ["codex", "debug", "models", "--bundled"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)["models"]


def build_catalog(bundled: list[dict], extra: list[dict]) -> dict:
    template = next((m for m in bundled if m.get("slug") == TEMPLATE_SLUG), bundled[0])
    extra_slugs = {row["value"] for row in extra}
    merged = [m for m in bundled if m.get("slug") not in extra_slugs]
    for row in extra:
        entry = dict(template)
        entry["slug"] = row["value"]
        entry["display_name"] = row.get("displayName", row["value"])
        entry["description"] = row.get("description", "")
        merged.append(entry)
    return {"models": merged}


def ensure_config_wired() -> bool:
    """Add model_catalog_json to config.toml if not already present. Returns True if changed."""
    text = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""
    if "model_catalog_json" in text:
        return False
    line = f'model_catalog_json = "{CATALOG_PATH}"\n'
    # must live at root level, before any [table] section
    lines = text.splitlines(keepends=True)
    insert_at = next((i for i, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
    lines.insert(insert_at, line)
    CONFIG_PATH.write_text("".join(lines), encoding="utf-8")
    return True


def apply() -> str:
    extra = load_extra()
    bundled = load_bundled()
    catalog = build_catalog(bundled, extra)
    CATALOG_PATH.write_text(json.dumps(catalog), encoding="utf-8")
    wired = ensure_config_wired()
    return (
        f"catalog: {CATALOG_PATH} ({len(catalog['models'])} models, "
        f"{len(extra)} from extra-models.json)\n"
        f"config.toml: {'updated' if wired else 'already wired'}"
    )


def status() -> str:
    wired = CONFIG_PATH.exists() and "model_catalog_json" in CONFIG_PATH.read_text(encoding="utf-8")
    return (
        f"catalog: {CATALOG_PATH} ({'exists' if CATALOG_PATH.exists() else 'missing'})\n"
        f"config.toml wired: {wired}\n"
        f"extra: {EXTRA_PATH} ({'yes' if EXTRA_PATH.exists() else 'missing'})"
    )


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "apply"
    if cmd == "status":
        print(status())
        return
    if cmd != "apply":
        raise SystemExit("usage: patch-model-catalog.py [apply|status]")
    print(apply())


if __name__ == "__main__":
    main()
