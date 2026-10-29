from pathlib import Path
import pytest

from loop.kernel.engine import LoopEngine
from loop.kernel.model import CursorStatus
from loop.tests.test_kernel import seed_project, _finish_via_gate, _seed_queue_implement_complete


def test_feature_epic_lifecycle_regression(tmp_path: Path) -> None:
    """Feature epic lifecycle remains intact and follows standard progression (TM-006, SC-005)."""
    paths = seed_project(tmp_path)
    engine = LoopEngine(paths)

    # 1. Start feature epic (default kind=feature)
    cursor = engine.start("E1")
    assert cursor.epic_id == "E1"
    assert cursor.kind == "feature"
    assert cursor.role == "back"
    assert cursor.phase == "IMPLEMENT"
    assert cursor.step_id == "s01"

    # 2. Finish s01 -> advances to s02
    t1 = _finish_via_gate(engine)
    assert t1.phase == "IMPLEMENT"
    assert t1.step_id == "s02"

    # 3. Mark implement artifacts complete so engine can advance past IMPLEMENT to QA
    _seed_queue_implement_complete(tmp_path, epic_id="E1")

    # 4. Finish s02 (last step in queue) -> moves to QA (AUDIT folded into QA)
    t2 = _finish_via_gate(engine)
    assert t2.phase == "QA"
    assert t2.step_id == "QA"
