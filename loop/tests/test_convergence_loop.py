import os
import logging
from unittest.mock import patch, MagicMock
import pytest

from epic.core import arm_epic
from epic.convergence import ConvergenceFinding

@pytest.fixture
def temp_project(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    mb = d / "memory-bank" / "back" / "plan" / "decompose-T-TEST-001"
    mb.mkdir(parents=True)
    (mb / "index.yaml").write_text("steps: []\n")
    return d

def test_arm_warn_on_flag(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    with patch.dict(os.environ, {"EPIC_CONVERGENCE_CHECK": "1"}):
        with patch("epic.core.run_convergence_checks") as mock_chk:
            mock_chk.return_value = [
                ConvergenceFinding(
                    id="F01",
                    category="traceability",
                    severity="HIGH",
                    message="Unlinked AC requirement",
                )
            ]
            with patch("board_sync.epic_resolver.resolve_epic_next_action") as mock_res:
                mock_action = MagicMock()
                mock_action.phase = "IMPLEMENT"
                mock_action.decompose_rel = "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
                mock_res.return_value = mock_action
                with patch("epic_transition.arm_phase") as mock_arm:
                    mock_arm.return_value = {"ok": True, "phase": "IMPLEMENT"}

                    res = arm_epic(tmp_path, "T-TEST-001", role="back")
                    assert mock_chk.called
                    assert "convergence" in caplog.text.lower() or "HIGH" in caplog.text

def test_arm_no_call_without_flag(tmp_path):
    env_copy = os.environ.copy()
    env_copy.pop("EPIC_CONVERGENCE_CHECK", None)
    with patch.dict(os.environ, env_copy, clear=True):
        with patch("epic.core.run_convergence_checks") as mock_chk:
            with patch("board_sync.epic_resolver.resolve_epic_next_action") as mock_res:
                mock_action = MagicMock()
                mock_action.phase = "IMPLEMENT"
                mock_action.decompose_rel = "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
                mock_res.return_value = mock_action
                with patch("epic_transition.arm_phase") as mock_arm:
                    mock_arm.return_value = {"ok": True, "phase": "IMPLEMENT"}

                    res = arm_epic(tmp_path, "T-TEST-001", role="back")
                    assert not mock_chk.called

def test_arm_warn_only_not_block(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    with patch.dict(os.environ, {"EPIC_CONVERGENCE_CHECK": "1"}):
        with patch("epic.core.run_convergence_checks") as mock_chk:
            mock_chk.return_value = [
                ConvergenceFinding(
                    id="F02",
                    category="traceability",
                    severity="CRITICAL",
                    message="Critical breakage",
                )
            ]
            with patch("board_sync.epic_resolver.resolve_epic_next_action") as mock_res:
                mock_action = MagicMock()
                mock_action.phase = "IMPLEMENT"
                mock_action.decompose_rel = "memory-bank/back/plan/decompose-T-TEST-001/index.yaml"
                mock_res.return_value = mock_action
                with patch("epic_transition.arm_phase") as mock_arm:
                    mock_arm.return_value = {"ok": True, "phase": "IMPLEMENT"}

                    res = arm_epic(tmp_path, "T-TEST-001", role="back")
                    assert res.get("ok") is True
