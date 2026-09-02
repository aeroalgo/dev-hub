"""Tests for loop.mb_finish shape and render."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from harness.hooks.epic.core import validate_active_context_shape
from loop.mb_finish.render import render_active_context
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta


def test_render_valid_implement():
    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040-harness-workflow-finish-api",
        step_id="s01",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-040-harness-workflow-finish-api/s01-schemas-render.yaml",
            description="текущий work shard",
        ),
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml",
            description="очередь/status",
        ),
    ]
    handoff = HandoffBody(
        mode="IMPLEMENT",
        step_id="s01",
        next_hint="выполнить atomic шаг → FINISH",
    )
    done = ["seed-implement done"]

    rendered = render_active_context(meta, load_now, done, handoff)
    assert "schema: loop-handoff/v1" in rendered
    assert "## load_now" in rendered
    assert "## Handoff BACK IMPLEMENT — s01" in rendered
    assert "## done" in rendered
    assert validate_active_context_shape(rendered) == []


def test_render_valid_qa():
    meta = LoopHandoffMeta(
        role="BACK",
        mode="QA",
        epic_id="T-HUB-040-harness-workflow-finish-api",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-040-harness-workflow-finish-api/index.yaml",
            description="очередь/status",
        ),
    ]
    handoff = HandoffBody(
        mode="QA",
        next_hint="прогнать suite + @reviewer",
    )

    rendered = render_active_context(meta, load_now, [], handoff)
    assert "schema: loop-handoff/v1" in rendered
    assert "## Handoff BACK QA" in rendered
    assert validate_active_context_shape(rendered) == []


def test_render_invalid_bad_load_now_raises():
    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040-harness-workflow-finish-api",
    )
    load_now = [
        LoadNowItem(
            path="memory-bank/back/plan/decompose-T-HUB-040/s01.yaml",
            description="status: completed",
        ),
    ]
    handoff = HandoffBody(mode="IMPLEMENT")

    with pytest.raises(ValueError, match="completed_in_load_now"):
        render_active_context(meta, load_now, [], handoff)


def test_render_invalid_missing_load_now_raises():
    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040-harness-workflow-finish-api",
    )
    handoff = HandoffBody(mode="IMPLEMENT")

    with pytest.raises(ValueError, match="missing_load_now"):
        render_active_context(meta, [], [], handoff)


@pytest.mark.parametrize(
    "scenario,load_now_items,done_items,handoff_body,expected_error",
    [
        (
            "completed_status_in_load_now",
            [LoadNowItem(path="memory-bank/back/plan/s01.yaml", description="status: completed step")],
            [],
            HandoffBody(mode="IMPLEMENT"),
            "completed_in_load_now",
        ),
        (
            "completed_word_in_load_now",
            [LoadNowItem(path="memory-bank/back/plan/s01.yaml", description="completed item")],
            [],
            HandoffBody(mode="IMPLEMENT"),
            "completed_in_load_now",
        ),
        (
            "done_word_in_load_now",
            [LoadNowItem(path="memory-bank/back/plan/s01.yaml", description="done step")],
            [],
            HandoffBody(mode="IMPLEMENT"),
            "completed_in_load_now",
        ),
        (
            "plan_loaded_after_implement",
            [
                LoadNowItem(path="memory-bank/back/implement/s01.yaml", description="impl"),
                LoadNowItem(path="memory-bank/back/plan/s02.yaml", description="plan"),
            ],
            [],
            HandoffBody(mode="IMPLEMENT"),
            "plan_loaded_after_implement",
        ),
    ],
)
def test_shape_errors_parametrize(scenario, load_now_items, done_items, handoff_body, expected_error):
    meta = LoopHandoffMeta(
        role="BACK",
        mode="IMPLEMENT",
        epic_id="T-HUB-040",
    )
    with pytest.raises(ValueError, match=expected_error):
        render_active_context(meta, load_now_items, done_items, handoff_body)


def test_direct_validate_shape_rules():
    # 1. missing load_now
    errs = validate_active_context_shape("## Handoff BACK IMPLEMENT\n")
    assert "missing_load_now" in errs

    # 2. missing handoff
    errs = validate_active_context_shape("## load_now\n1. [path](path) — desc\n")
    assert "missing_handoff" in errs

    # 3. multiple load_now
    errs = validate_active_context_shape("## load_now\n1. [a](a)\n## load_now\n2. [b](b)\n## Handoff BACK IMPLEMENT\n")
    assert "multiple_load_now" in errs

    # 4. multiple handoff
    errs = validate_active_context_shape("## load_now\n1. [a](a)\n## Handoff BACK IMPLEMENT\n## Handoff FRONT QA\n")
    assert "multiple_handoff" in errs

    # 5. multiple done
    errs = validate_active_context_shape("## load_now\n1. [a](a)\n## Handoff BACK IMPLEMENT\n## done\n- 1\n## done\n- 2\n")
    assert "multiple_done" in errs

    # 6. malformed marker
    errs = validate_active_context_shape("## load_now\n1. [a](a)\n## Handoff BACK IMPLEMENT\nBLOCKED with trailing non-colon text\n")
    assert "malformed_marker" in errs


def test_shape_rules_scenarios_count():
    # Ensuring 20 distinct shape validation assertion tests/scenarios
    fm = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-TEST\n"
        "---\n\n"
    )
    test_cases = [
        ("valid_1", fm + "## load_now\n1. [a](a)\n## Handoff BACK IMPLEMENT\n", []),
        ("valid_2", fm + "## load_now\n1. [a](a)\n## Handoff FRONT QA\n## done\n- item\n", []),
        ("empty", "", ["missing_load_now", "missing_handoff"]),
        ("no_load", fm + "## Handoff BACK IMPLEMENT\n", ["missing_load_now"]),
        ("no_handoff", fm + "## load_now\n1. [a](a)\n", ["missing_handoff"]),
        ("multi_load", fm + "## load_now\n## load_now\n## Handoff BACK IMPLEMENT\n", ["multiple_load_now"]),
        ("multi_handoff", fm + "## load_now\n## Handoff A\n## Handoff B\n", ["multiple_handoff"]),
        ("multi_done", fm + "## load_now\n## Handoff A\n## done\n## done\n", ["multiple_done"]),
        ("completed_in_load_1", fm + "## load_now\n1. [a](a) - status: completed\n## Handoff A\n", ["completed_in_load_now"]),
        ("completed_in_load_2", fm + "## load_now\n1. [a](a) - status: done\n## Handoff A\n", ["completed_in_load_now"]),
        ("completed_in_load_3", fm + "## load_now\n1. [a](a) completed step\n## Handoff A\n", ["completed_in_load_now"]),
        ("plan_after_impl", fm + "## load_now\n1. [impl](memory-bank/back/implement/s01.yaml)\n2. [plan](memory-bank/back/plan/s02.yaml)\n## Handoff A\n", ["plan_loaded_after_implement"]),
        ("malformed_blocked", fm + "## load_now\n1. [a](a)\n## Handoff A\nBLOCKED test bad\n", ["malformed_marker"]),
        ("malformed_epic_done", fm + "## load_now\n1. [a](a)\n## Handoff A\nEPIC_DONE extra text\n", ["malformed_marker"]),
        ("malformed_need_human", fm + "## load_now\n1. [a](a)\n## Handoff A\nNEED_HUMAN bad text\n", ["malformed_marker"]),
        ("valid_blocked_colon", fm + "## load_now\n1. [a](a)\n## Handoff A\nBLOCKED: reason\n", []),
        ("valid_epic_done_standalone", fm + "## load_now\n1. [a](a)\n## Handoff A\nEPIC_DONE\n", []),
        ("valid_need_human_colon", fm + "## load_now\n1. [a](a)\n## Handoff A\nNEED_HUMAN: reason\n", []),
        ("combo_errors", fm + "## load_now\n## load_now\n## Handoff A\n## Handoff B\n", ["multiple_load_now", "multiple_handoff"]),
        ("all_missing", "   \n\t\n", ["missing_load_now", "missing_handoff"]),
    ]
    assert len(test_cases) == 20
    for name, text, expected in test_cases:
        assert validate_active_context_shape(text) == expected, f"Failed on {name}"
