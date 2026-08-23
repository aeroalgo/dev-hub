from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def test_needs_creative_open_forces_creative():
    from epic_lib import effective_phase, gates_from_phase

    phase = effective_phase(
        role="BACK",
        next_phase="BACK IMPLEMENT",
        needs_creative="yes (CR-ELIB-1)",
    )

    assert phase == "BACK CREATIVE"
    assert gates_from_phase(phase) == {
        "mode": "creative",
        "need_verify": False,
        "need_reviewer": False,
    }


def test_return_to_implement_when_needs_creative_closed():
    from epic_lib import effective_phase

    assert effective_phase(
        role="BACK",
        next_phase="BACK IMPLEMENT",
        needs_creative="yes (CR-ELIB-1) — closed",
    ) == "BACK IMPLEMENT"


def test_closed_needs_creative_overrides_stale_creative_next_phase():
    from epic_lib import effective_phase

    assert (
        effective_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative="yes (CR-ELIB-1) ✅",
        )
        == "BACK IMPLEMENT"
    )
    assert (
        effective_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative="yes (CR-ELIB-1) — **closed**",
        )
        == "BACK IMPLEMENT"
    )


def test_return_to_implement_after_creative_step():
    from epic_lib import effective_phase

    assert effective_phase(
        role="BACK", next_phase="BACK IMPLEMENT", needs_creative=None
    ) == "BACK IMPLEMENT"


def test_missing_needs_creative_keeps_explicit_creative_next_phase():
    from epic_lib import effective_phase

    assert (
        effective_phase(
            role="BACK",
            next_phase="BACK CREATIVE",
            needs_creative=None,
        )
        == "BACK CREATIVE"
    )
