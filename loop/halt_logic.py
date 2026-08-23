"""Pure halt/continue/complete decision after check-after JSON."""

from __future__ import annotations

from typing import Any, Literal

DecideAction = Literal["halt", "complete", "continue"]


def _truthy_halt(value: Any) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes"}:
        return True
    return False


def decide_after_action(after_json: dict) -> DecideAction:
    """Map check-after JSON to shell action (fail-closed).

    Priority (Halt matrix):
      1. halt flag (bool/int/string '1') → halt
      2. stop starts with NEED_HUMAN → halt
      3. stop == EPIC_DONE → complete
      4. repair_exhausted / non-retryable integrity → halt
      5. ok (continue path) → continue
      6. unknown → halt
    """
    if not isinstance(after_json, dict):
        return "halt"

    if _truthy_halt(after_json.get("halt")):
        return "halt"

    stop = after_json.get("stop")
    if isinstance(stop, str):
        if stop.startswith("NEED_HUMAN"):
            return "halt"
        if stop == "EPIC_DONE":
            return "complete"

    if after_json.get("repair_exhausted"):
        return "halt"

    if after_json.get("ok") is True and after_json.get("complete") is not True:
        return "continue"

    if after_json.get("ok") is True and after_json.get("complete") is True:
        # complete without EPIC_DONE / NEED_HUMAN already handled → fail-closed
        return "halt"

    return "halt"
