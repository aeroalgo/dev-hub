from __future__ import annotations

from harness.hooks.loop_guard import hooks_enabled, is_loop_process


def test_hooks_are_disabled_without_loop_marker() -> None:
    assert is_loop_process({}) is False
    assert hooks_enabled({}) is False


def test_hooks_are_enabled_only_for_active_loop() -> None:
    env = {"LOOP_ACTIVE": "1", "EPIC_LOOP": "1", "LOOP_WORKFLOW_HOOKS": "loop"}

    assert is_loop_process(env) is True
    assert hooks_enabled(env) is True
    assert hooks_enabled({**env, "LOOP_WORKFLOW_HOOKS": "off"}) is False
