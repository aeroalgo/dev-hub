#!/usr/bin/env python3
import json
import sys

from pathlib import Path

HOOKS = Path(__file__).resolve().parents[2] / "harness" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from loop_guard import hooks_enabled  # noqa: E402

if hooks_enabled():
    sys.stdout.write(json.dumps({"continue": True}))
