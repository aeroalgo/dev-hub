"""Patch CLAUDE.md with dev-hub harness marker block while preserving user content."""

import argparse
import hashlib
from pathlib import Path
from typing import Union

BEGIN_MARKER = "<!-- dev-hub:harness:begin -->"
END_MARKER = "<!-- dev-hub:harness:end -->"

DEFAULT_HARNESS_BLOCK = """# dev-hub harness entry
- **Harness role commands:** `BACK`, `FRONT`, `INTEG`
- **Rules & workflows:** `harness/cursor/rules/`
- **Claude Code harness config:** `harness/claude/`
"""


def patch_claude_md(path: Union[str, Path], harness_block_content: str = DEFAULT_HARNESS_BLOCK) -> bool:
    """Patch or create CLAUDE.md with marker block.

    Returns True if file was modified or created, False if unchanged.
    """
    target = Path(path)
    # Ensure harness block is trimmed but properly formatted
    inner_text = harness_block_content.strip("\n")
    full_block = f"{BEGIN_MARKER}\n{inner_text}\n{END_MARKER}\n"

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(full_block, encoding="utf-8")
        return True

    original = target.read_text(encoding="utf-8")

    if BEGIN_MARKER in original and END_MARKER in original:
        begin_idx = original.find(BEGIN_MARKER)
        end_idx = original.find(END_MARKER) + len(END_MARKER)
        # Check trailing newline after end marker if present
        if end_idx < len(original) and original[end_idx] == "\n":
            end_idx += 1

        new_content = original[:begin_idx] + full_block + original[end_idx:]
    elif BEGIN_MARKER in original or END_MARKER in original:
        # Partial marker corrupted: replace from marker to end or append
        new_content = original.rstrip() + "\n\n" + full_block
    else:
        # No markers present: append at end
        separator = "\n\n" if original and not original.endswith("\n\n") else ("\n" if original and not original.endswith("\n") else "")
        new_content = original + separator + full_block

    if new_content == original:
        return False

    target.write_text(new_content, encoding="utf-8")
    return True


def strip_claude_md_block(path: Union[str, Path]) -> bool:
    """Remove marker block from CLAUDE.md.

    If file only contains marker block (or whitespace), deletes the file or empties it.
    Returns True if file was modified or removed, False if no markers found / unchanged.
    """
    target = Path(path)
    if not target.exists():
        return False

    original = target.read_text(encoding="utf-8")
    if BEGIN_MARKER not in original and END_MARKER not in original:
        return False

    if BEGIN_MARKER in original and END_MARKER in original:
        begin_idx = original.find(BEGIN_MARKER)
        end_idx = original.find(END_MARKER) + len(END_MARKER)
        if end_idx < len(original) and original[end_idx] == "\n":
            end_idx += 1
        new_content = original[:begin_idx] + original[end_idx:]
    elif BEGIN_MARKER in original:
        begin_idx = original.find(BEGIN_MARKER)
        new_content = original[:begin_idx]
    else:
        end_idx = original.find(END_MARKER) + len(END_MARKER)
        if end_idx < len(original) and original[end_idx] == "\n":
            end_idx += 1
        new_content = original[end_idx:]

    # Clean up excess trailing whitespace if we removed at the end
    cleaned = new_content.strip()
    if not cleaned:
        target.unlink(missing_ok=True)
        return True

    # If non-empty, ensure clean ending newline
    target.write_text(cleaned + "\n", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch or strip dev-hub harness markers from CLAUDE.md.")
    parser.add_argument("path", help="Path to CLAUDE.md")
    parser.add_argument("--strip", action="store_true", help="Strip marker block instead of patching")
    parser.add_argument("--block-file", help="Path to custom harness block content file", default=None)
    args = parser.parse_args()

    if args.strip:
        changed = strip_claude_md_block(args.path)
        if changed:
            print(f"stripped {args.path}")
        else:
            print(f"unchanged {args.path}")
        return

    content = DEFAULT_HARNESS_BLOCK
    if args.block_file:
        content = Path(args.block_file).read_text(encoding="utf-8")

    changed = patch_claude_md(args.path, content)
    if changed:
        print(f"patched {args.path}")
    else:
        print(f"unchanged {args.path}")


if __name__ == "__main__":
    main()
