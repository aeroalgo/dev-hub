from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


HOOK_EVENTS = {
    "SessionStart": "session-start.py",
    "UserPromptSubmit": "user-prompt.py",
    "PreToolUse": "pretool-dispatch.py",
    "PostToolUse": "posttool-dispatch.py",
    "SubagentStart": "subagent-start.py",
    "SubagentStop": "subagent-stop.py",
    "Stop": "stop-gate.py",
}


def _hooks_payload() -> dict[str, Any]:
    hooks: dict[str, list[dict[str, Any]]] = {}
    for event, script in HOOK_EVENTS.items():
        item: dict[str, Any] = {
            "type": "command",
            "command": f"python3 harness/hooks/{script}",
        }
        if event in {"PreToolUse", "PostToolUse"}:
            item["matcher"] = ".*"
        if event == "PostToolUse":
            item["timeout_ms"] = 45000
        hooks[event] = [item]
    return {"hooks": hooks}


def _manifest(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"invalid manifest: {path}")
    return payload


def _drift(root: Path, manifest_path: Path, hooks_path: Path) -> list[str]:
    issues: list[str] = []
    if not hooks_path.is_file():
        issues.append(f"missing hooks file: {hooks_path}")
    else:
        try:
            actual = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(f"invalid hooks JSON: {hooks_path}")
        else:
            if actual != _hooks_payload():
                issues.append(f"hooks drift: {hooks_path}")

    manifest = _manifest(manifest_path)
    for agent_id, definition in (manifest.get("agents") or {}).items():
        if not isinstance(definition, dict):
            issues.append(f"invalid agent definition: {agent_id}")
            continue
        runtime = ((definition.get("runtimes") or {}).get("codex") or {})
        if runtime.get("materialize"):
            target = root / str(runtime.get("target") or "")
            if not target.is_file():
                issues.append(f"missing codex agent: {target}")
    for script in HOOK_EVENTS.values():
        path = root / "harness" / "hooks" / script
        if not path.is_file():
            issues.append(f"missing hook entrypoint: {path}")
    return issues


def _apply(root: Path, hooks_path: Path) -> None:
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(
        json.dumps(_hooks_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate loop runtime materialization")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--hooks-json", type=Path)
    parser.add_argument("--root-dir", type=Path)
    parser.add_argument("--runtime", choices=("codex", "claude", "all"), default="codex")
    parser.add_argument("--allow-hash-mismatch", action="store_true")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    root = (args.root_dir or Path(__file__).resolve().parents[2]).resolve()
    manifest_path = (args.manifest or root / "harness" / "manifest.yaml").resolve()
    hooks_path = (args.hooks_json or root / ".codex" / "hooks.json").resolve()
    if not manifest_path.is_file():
        print(f"Manifest file not found: {manifest_path}", file=sys.stderr)
        return 1
    if args.runtime == "claude":
        return 0
    issues = _drift(root, manifest_path, hooks_path)
    if args.apply:
        _apply(root, hooks_path)
        issues = _drift(root, manifest_path, hooks_path)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("No drift detected" if args.check else "Applied runtime 'codex'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
