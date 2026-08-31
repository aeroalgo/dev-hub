"""halt_logic treats ARCHIVE_DONE like EPIC_DONE complete."""

from loop.halt_logic import decide_after_action


def test_archive_done_maps_to_complete() -> None:
    assert decide_after_action({"ok": True, "complete": True, "stop": "ARCHIVE_DONE"}) == "complete"


def test_archive_done_not_halt_when_ok_complete() -> None:
    assert decide_after_action({"ok": True, "complete": True, "stop": "ARCHIVE_DONE", "halt": False}) == "complete"
