#!/usr/bin/env python3
"""Canonical PreToolUse hook dispatcher.
Consolidates boundary checks, agent/task spawn policy, bash policy, and write policy
into an ordered, fail-closed dispatch pipeline.
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
from hook_dispatch import EventContext, PreToolUse, dispatch_pretool
from pretool_policy import create_pretool_branches


def main() -> None:
    data = read_stdin()
    context = EventContext.from_payload(data, default_event=PreToolUse)
    branches = create_pretool_branches()
    envelope = dispatch_pretool(context, branches)
    emit(envelope.to_hook_output(PreToolUse))


if __name__ == "__main__":
    main()
