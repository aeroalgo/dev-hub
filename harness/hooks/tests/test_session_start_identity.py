"""Tests for SessionStart identity lock and fixture 94cea2d3 reproduction (T-HUB-071)."""

from unittest.mock import patch
import pytest
from harness.hooks.epic.core import session_start_payload
from loop.mb_load.schemas import MbLoadResult, MbLoadFile


def test_fixture_94cea2d3_armed_bugfix_stale_qa_ac_drift_halt(monkeypatch, tmp_path):
    """FR-014 / US-001 / US-003: Fixture 94cea2d3 reproduction.

    When state is armed for BUGFIX, but activeContext has stale QA mode:
    session_start_payload must emit CONTEXT_IDENTITY_DRIFT halt card,
    and must NOT emit dual commands (e.g. COMMAND BACK QA alongside intended BUGFIX).
    """
    monkeypatch.setenv("EPIC_LOOP", "1")

    # Armed state is BUGFIX
    state = {
        "active": "T-HUB-071",
        "status": "running",
        "phase": "BUGFIX",
        "role": "BACK",
        "armed_step": "BUGFIX",
        "projection": {"phase": "BACK BUGFIX", "role": "BACK", "step": "BUGFIX", "epic": "T-HUB-071"},
    }

    # Stale activeContext with QA frontmatter
    stale_active_context = (
        "---\n"
        "mode: QA\n"
        "role: BACK\n"
        "epic_id: T-HUB-071\n"
        "---\n"
        "# Active Context\n"
        "## Handoff BACK QA\n"
    )

    with patch("harness.hooks.epic.core.load_epic_state", return_value=state), \
         patch("harness.hooks.epic.core.read_active_context", return_value=stale_active_context), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp94cea2d3",
            files=[MbLoadFile(path="file1.txt", content="content", size_bytes=7, sha256="abc")]
        )

        res = session_start_payload(tmp_path)
        assert res is not None, "session_start_payload should return a payload dict"
        ctx = res.get("additionalContext", "")

        # Must trigger CONTEXT_IDENTITY_DRIFT and halt card
        assert "CONTEXT_IDENTITY_DRIFT" in ctx, (
            f"Expected CONTEXT_IDENTITY_DRIFT in additionalContext due to state BUGFIX vs AC QA mismatch. Got:\n{ctx}"
        )
        assert "HALT" in ctx, f"Expected HALT card in additionalContext. Got:\n{ctx}"

        # Must NOT emit COMMAND: BACK QA
        assert "COMMAND: BACK QA" not in ctx, "Must not emit COMMAND: BACK QA when armed in BUGFIX"


def test_armed_bugfix_single_command_back_bugfix_no_second_command_qa(monkeypatch, tmp_path):
    """US-001 / FR-019: When state, projection, and AC are all aligned to BUGFIX,

    payload contains exactly 'COMMAND: BACK BUGFIX' and no second COMMAND.
    """
    monkeypatch.setenv("EPIC_LOOP", "1")

    state = {
        "active": "T-HUB-071",
        "status": "running",
        "phase": "BUGFIX",
        "role": "BACK",
        "armed_step": "BUGFIX",
        "projection": {"phase": "BACK BUGFIX", "role": "BACK", "step": "BUGFIX", "epic": "T-HUB-071"},
    }

    aligned_active_context = (
        "---\n"
        "mode: BUGFIX\n"
        "role: BACK\n"
        "epic_id: T-HUB-071\n"
        "---\n"
        "# Active Context\n"
        "## Handoff BACK BUGFIX\n"
    )

    with patch("harness.hooks.epic.core.load_epic_state", return_value=state), \
         patch("harness.hooks.epic.core.read_active_context", return_value=aligned_active_context), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp12345",
            files=[MbLoadFile(path="f.txt", content="x", size_bytes=1, sha256="1")]
        )

        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res.get("additionalContext", "")
        # Check command count (≤ 1 COMMAND: in additionalContext)
        command_lines = [line for line in ctx.splitlines() if line.startswith("COMMAND:")]
        assert len(command_lines) == 1, f"Expected exactly 1 COMMAND: line, found: {command_lines}"
        assert command_lines[0] == "COMMAND: BACK BUGFIX"
        assert "COMMAND: BACK QA" not in ctx


def test_frontmatter_heading_not_used_as_command_when_frontmatter_valid(monkeypatch, tmp_path):
    """FR-007 / SC-005: When loop-handoff/v1 frontmatter is valid, heading is not used as COMMAND source."""
    monkeypatch.setenv("EPIC_LOOP", "1")

    state = {
        "active": "T-HUB-071",
        "status": "running",
        "phase": "IMPLEMENT",
        "role": "BACK",
        "armed_step": "s03",
        "projection": {"phase": "BACK IMPLEMENT", "role": "BACK", "step": "s03", "epic": "T-HUB-071"},
    }

    # Frontmatter says IMPLEMENT s03, but legacy markdown heading says QA
    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "mode: IMPLEMENT\n"
        "role: BACK\n"
        "epic_id: T-HUB-071\n"
        "step_id: s03\n"
        "---\n"
        "# Active Context\n"
        "## Handoff BACK QA\n"
    )

    with patch("harness.hooks.epic.core.load_epic_state", return_value=state), \
         patch("harness.hooks.epic.core.read_active_context", return_value=active_context), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp12345",
            files=[MbLoadFile(path="f.txt", content="x", size_bytes=1, sha256="1")]
        )

        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res.get("additionalContext", "")
        assert "COMMAND: BACK IMPLEMENT" in ctx
        assert "COMMAND: BACK QA" not in ctx


def test_epic_phase_mismatch_halt(monkeypatch, tmp_path):
    """FR-005: expected_identity from EPIC_PHASE must match state, else halt."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("EPIC_PHASE", "QA")

    state = {
        "active": "T-HUB-071",
        "status": "running",
        "phase": "IMPLEMENT",
        "role": "BACK",
        "armed_step": "s03",
        "projection": {"phase": "BACK IMPLEMENT", "role": "BACK", "step": "s03", "epic": "T-HUB-071"},
    }

    active_context = (
        "---\n"
        "schema: loop-handoff/v1\n"
        "mode: IMPLEMENT\n"
        "role: BACK\n"
        "epic_id: T-HUB-071\n"
        "step_id: s03\n"
        "---\n"
        "# Active Context\n"
        "## Handoff BACK IMPLEMENT\n"
    )

    with patch("harness.hooks.epic.core.load_epic_state", return_value=state), \
         patch("harness.hooks.epic.core.read_active_context", return_value=active_context), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp12345",
            files=[MbLoadFile(path="f.txt", content="x", size_bytes=1, sha256="1")]
        )

        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res.get("additionalContext", "")
        assert "CONTEXT_IDENTITY_DRIFT" in ctx
        assert "HALT" in ctx
        assert "code: phase_mismatch" in ctx
