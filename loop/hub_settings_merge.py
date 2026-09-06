"""Deep merge harness hooks into user settings.json preserving user permissions and settings."""

import argparse
import json
import re
import shlex
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def canonicalize_command(cmd_str: str, project_dir: Optional[Union[str, Path]] = None) -> str:
    """Canonicalize a hook command by resolving script paths relative to project_dir."""
    if not cmd_str:
        return ""
    p_dir = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()

    # Expand $CLAUDE_PROJECT_DIR or ${CLAUDE_PROJECT_DIR}
    expanded = cmd_str.replace("$CLAUDE_PROJECT_DIR", str(p_dir)).replace("${CLAUDE_PROJECT_DIR}", str(p_dir))

    try:
        tokens = shlex.split(expanded)
    except ValueError:
        tokens = expanded.split()

    canon_tokens = []
    for token in tokens:
        token_path = Path(token)
        # If absolute or relative to project_dir and exists (or is inside project)
        if token_path.is_absolute():
            try:
                resolved = token_path.resolve()
                canon_tokens.append(str(resolved))
                continue
            except Exception:
                pass
        else:
            rel_candidate = (p_dir / token_path)
            if rel_candidate.exists():
                try:
                    resolved = rel_candidate.resolve()
                    canon_tokens.append(str(resolved))
                    continue
                except Exception:
                    pass
        canon_tokens.append(token)
    return " ".join(canon_tokens)


def _extract_hook_commands(hook_dict: Dict[str, Any]) -> List[str]:
    """Extract command strings from nested hook structure."""
    cmds = []
    nested_hooks = hook_dict.get("hooks", [])
    if isinstance(nested_hooks, list):
        for h in nested_hooks:
            if isinstance(h, dict) and "command" in h:
                cmds.append(str(h["command"]))
    return cmds


def _extract_canon_commands(hook_dict: Dict[str, Any], project_dir: Optional[Union[str, Path]] = None) -> List[str]:
    """Extract canonicalized command strings from nested hook structure."""
    cmds = _extract_hook_commands(hook_dict)
    return [canonicalize_command(cmd, project_dir=project_dir) for cmd in cmds]


def find_duplicate_hook_realpaths(
    settings_input: Union[str, Path, Dict[str, Any]],
    project_dir: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Scan settings for duplicate command realpaths under the same (event, matcher)."""
    if isinstance(settings_input, (str, Path)):
        s_path = Path(settings_input)
        if not s_path.exists():
            return []
        data = json.loads(s_path.read_text(encoding="utf-8"))
    else:
        data = settings_input

    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return []

    duplicates = []
    for event_name, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        # Group by matcher
        by_matcher: Dict[Optional[str], List[Tuple[str, str]]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher")
            raw_cmds = _extract_hook_commands(entry)
            for raw_cmd in raw_cmds:
                canon = canonicalize_command(raw_cmd, project_dir=project_dir)
                by_matcher.setdefault(matcher, []).append((raw_cmd, canon))

        for matcher, cmd_pairs in by_matcher.items():
            seen_canon: Dict[str, str] = {}
            for raw_cmd, canon in cmd_pairs:
                if canon in seen_canon:
                    duplicates.append({
                        "event": event_name,
                        "matcher": matcher,
                        "canonical": canon,
                        "first_command": seen_canon[canon],
                        "duplicate_command": raw_cmd,
                    })
                else:
                    seen_canon[canon] = raw_cmd
    return duplicates


def check_settings_unique_realpaths(
    settings_input: Union[str, Path, Dict[str, Any]],
    project_dir: Optional[Union[str, Path]] = None,
) -> None:
    """Raise ValueError(hook_duplicate_realpath) if any duplicate command realpaths exist."""
    duplicates = find_duplicate_hook_realpaths(settings_input, project_dir=project_dir)
    if duplicates:
        raise ValueError(f"hook_duplicate_realpath: found duplicates: {duplicates}")


def _hook_entry_matches(
    entry_a: Dict[str, Any],
    entry_b: Dict[str, Any],
    project_dir: Optional[Union[str, Path]] = None,
) -> bool:
    """Check if two hook entries match in matcher and inner commands (realpath aware)."""
    if entry_a.get("matcher") != entry_b.get("matcher"):
        return False
    canon_a = _extract_canon_commands(entry_a, project_dir=project_dir)
    canon_b = _extract_canon_commands(entry_b, project_dir=project_dir)
    if canon_a and canon_b:
        return set(canon_a) == set(canon_b)
    return entry_a == entry_b


def merge_hooks(
    user_hooks: Dict[str, Any],
    harness_hooks: Dict[str, Any],
    project_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
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
            h_canons = _extract_canon_commands(h_entry, project_dir=project_dir)
            duplicate_found = False
            for u_entry in result_entries:
                if not isinstance(u_entry, dict):
                    continue
                if _hook_entry_matches(u_entry, h_entry, project_dir=project_dir):
                    duplicate_found = True
                    break
                u_canons = _extract_canon_commands(u_entry, project_dir=project_dir)
                if h_canons and u_canons and u_entry.get("matcher") == h_entry.get("matcher"):
                    # If all canonical commands in h_entry already present in u_entry, consider duplicate
                    if all(cmd in u_canons for cmd in h_canons):
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

    # Infer project_dir from user_path parent if user_path is in .claude/settings.json
    project_dir = u_path.parent.parent if u_path.parent.name == ".claude" else u_path.parent
    merged_hooks = merge_hooks(user_hooks, harness_hooks, project_dir=project_dir)

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
