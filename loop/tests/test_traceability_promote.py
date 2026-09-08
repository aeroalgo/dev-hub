"""Tests for traceability default fail-closed behavior on DECOMPOSE promote."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from loop.context_loop import (
    run_traceability_check_if_enabled,
)


def test_traceability_default_decompose(monkeypatch, tmp_path: Path):
    """cp1: unset + fail_closed=True → traceability runs."""
    monkeypatch.delenv("EPIC_TRACEABILITY_CHECK", raising=False)

    with patch("subprocess.run") as mock_run, patch("loop.context_loop.load_epic_state") as mock_state:
        mock_state.return_value = {"armed_epic": "T-TEST", "role": "back"}
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_traceability_check_if_enabled(tmp_path, "T-TEST", fail_closed=True)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "validate-traceability" in cmd
        assert "T-TEST" in cmd


def test_traceability_explicit_zero(monkeypatch, tmp_path: Path):
    """cp2: EPIC_TRACEABILITY_CHECK=0 → explicit skip."""
    monkeypatch.setenv("EPIC_TRACEABILITY_CHECK", "0")

    with patch("subprocess.run") as mock_run:
        run_traceability_check_if_enabled(tmp_path, "T-TEST", fail_closed=True)
        assert not mock_run.called
