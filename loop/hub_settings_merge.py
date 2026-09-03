"""Deep merge harness hooks into user settings.json preserving user permissions and settings."""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Union


def _extract_hook_commands(hook_dict: Dict[str, Any]) -> List[str]:
    """Extract command strings from nested hook structure."""
    cmds = []
    nested_hooks = hook_dict.get("hooks", [])
    if isinstance(nested_hooks, list):
        for h in nested_hooks:
            if isinstance(h, dict) and "command" in h:
                cmds.append(str(h["command"]))
    return cmds


def _hook_entry_matches(entry_a: Dict[str, Any], entry_b: Dict[str, Any]) -> bool:
    """Check if two hook entries match in matcher and inner commands."""
    if entry_a.get("matcher") != entry_b.get("matcher"):
        return False
    cmds_a = _extract_hook_commands(entry_a)
    cmds_b = _extract_hook_commands(entry_b)
    if cmds_a and cmds_b:
        return set(cmds_a) == set(cmds_b)
    return entry_a == entry_b


def merge_hooks(user_hooks: Dict[str, Any], harness_hooks: Dict[str, Any]) -> Dict[str, Any]:
    """Merge harness hooks into user hooks without duplicating existing hook commands."""
    merged = dict(user_hooks)
    for event_name, harness_entries in harness_hooks.items():
        if not isinstance(harness_entries, list):
            continue
        user_entries = merged.get(event_name, [])
        if not isinstance(user_entries, list):
            user_entries = []

        result_entries = list(user_entries)
        for h_entry in harness_entries:
            if not isinstance(h_entry, dict):
                continue
            # Check if this entry or its commands already exist in result_entries
            h_cmds = _extract_hook_commands(h_entry)
            duplicate_found = False
            for u_entry in result_entries:
                if not isinstance(u_entry, dict):
                    continue
                if _hook_entry_matches(u_entry, h_entry):
                    duplicate_found = True
                    break
                u_cmds = _extract_hook_commands(u_entry)
                if h_cmds and u_cmds and u_entry.get("matcher") == h_entry.get("matcher"):
                    # If all commands in h_entry already present in u_entry, consider duplicate
                    if all(cmd in u_cmds for cmd in h_cmds):
                        duplicate_found = True
                        break

            if not duplicate_found:
                result_entries.append(h_entry)

        merged[event_name] = result_entries
    return merged


def merge_settings(
    user_path: Union[str, Path],
    harness_path: Union[str, Path],
    backup: bool = True,
    force_permissions: bool = False,
) -> bool:
    """Merge harness settings into user settings.json.

    - Preserves user permissions (raises NotImplementedError if force_permissions=True)
    - Creates user_path.hub-backup if user_path already exists and backup=True
    - Deep-merges hooks section
    - If user_path does not exist, copies harness settings
    - Returns True if file was modified/created, False if unchanged
    """
    if force_permissions:
        raise NotImplementedError("force_permissions flag is deferred and not implemented")

    u_path = Path(user_path)
    h_path = Path(harness_path)

    if not h_path.exists():
        raise FileNotFoundError(f"Harness settings file not found: {h_path}")

    harness_content = h_path.read_text(encoding="utf-8")
    harness_json: Dict[str, Any] = json.loads(harness_content)

    if not u_path.exists():
        u_path.parent.mkdir(parents=True, exist_ok=True)
        u_path.write_text(harness_content, encoding="utf-8")
        return True

    user_content = u_path.read_text(encoding="utf-8")
    try:
        user_json: Dict[str, Any] = json.loads(user_content)
    except json.JSONDecodeError:
        user_json = {}

    # Deep-merge hooks
    user_hooks = user_json.get("hooks", {})
    if not isinstance(user_hooks, dict):
        user_hooks = {}
    harness_hooks = harness_json.get("hooks", {})
    if not isinstance(harness_hooks, dict):
        harness_hooks = {}

    merged_hooks = merge_hooks(user_hooks, harness_hooks)

    new_user_json = dict(user_json)
    # Ensure $schema is preserved or added if absent
    if "$schema" not in new_user_json and "$schema" in harness_json:
        new_user_json["$schema"] = harness_json["$schema"]
    new_user_json["hooks"] = merged_hooks

    # Check if there is any change
    new_content = json.dumps(new_user_json, indent=2, ensure_ascii=False) + "\n"
    if new_content == user_content:
        return False

    # Create backup before modifying
    if backup:
        backup_path = u_path.with_name(f"{u_path.name}.hub-backup")
        shutil.copy2(u_path, backup_path)

    u_path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge dev-hub harness hooks into user settings.json.")
    parser.add_argument("user_path", help="Path to user .claude/settings.json")
    parser.add_argument("harness_path", help="Path to harness/claude/settings.harness.json")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup file")
    args = parser.parse_args()

    changed = merge_settings(args.user_path, args.harness_path, backup=not args.no_backup)
    if changed:
        print(f"merged {args.user_path}")
    else:
        print(f"unchanged {args.user_path}")


if __name__ == "__main__":
    main()
