#!/usr/bin/env python3
"""Canonical PostToolUse hook dispatcher.
Consolidates agent evidence recording, in-flight cleanup, repair state release,
and Bash output capping/dumping into an ordered, disjoint dispatch pipeline.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_HUB_ROOT = _HOOKS_DIR.parents[1]
if str(_HUB_ROOT) not in sys.path:
    sys.path.insert(0, str(_HUB_ROOT))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _lib import emit, read_stdin
from hook_dispatch import EventContext, PostToolUse
from posttool_policy import dispatch_posttool_event


def main() -> None:
    data = read_stdin()
    context = EventContext.from_payload(data, default_event=PostToolUse)
    envelope = dispatch_posttool_event(context)

    output = envelope.to_hook_output(PostToolUse)
    if envelope.metadata:
        if "updatedToolOutput" in envelope.metadata:
            output.setdefault("hookSpecificOutput", {})["updatedToolOutput"] = envelope.metadata["updatedToolOutput"]
        if "additionalContext" in envelope.metadata:
            output.setdefault("hookSpecificOutput", {})["additionalContext"] = envelope.metadata["additionalContext"]
        elif "additional_context" in envelope.metadata:
            output.setdefault("hookSpecificOutput", {})["additionalContext"] = envelope.metadata["additional_context"]

    emit(output)


if __name__ == "__main__":
    main()
