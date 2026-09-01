import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pytest
from tests.architecture.check_boundaries import Violation, check_ratchet, RatchetResult


def test_ratchet_unchanged_count_passes(tmp_path: Path):
    ratchet_file = tmp_path / "ratchet.json"
    ratchet_file.write_text('{"violations": 0}', encoding="utf-8")

    violations = []
    res = check_ratchet(violations, ratchet_file)
    assert res.ok is True
    assert res.delta == 0
    assert res.message == ""


def test_ratchet_increase_blocked(tmp_path: Path):
    ratchet_file = tmp_path / "ratchet.json"
    ratchet_file.write_text('{"violations": 0}', encoding="utf-8")

    violations = [
        Violation(
            contract_id="c1",
            file_path="foo.py",
            line_number=1,
            imported_module="bad",
            forbidden_pattern="bad",
            reason="reason",
        ),
        Violation(
            contract_id="c2",
            file_path="bar.py",
            line_number=2,
            imported_module="bad2",
            forbidden_pattern="bad2",
            reason="reason",
        ),
        Violation(
            contract_id="c3",
            file_path="baz.py",
            line_number=3,
            imported_module="bad3",
            forbidden_pattern="bad3",
            reason="reason",
        ),
    ]

    res = check_ratchet(violations, ratchet_file)
    assert res.ok is False
    assert res.delta == 3
    assert "RATCHET EXCEEDED: found 3, allowed 0; run update-ratchet to freeze new baseline" in res.message


def test_ratchet_decrease_allowed(tmp_path: Path):
    ratchet_file = tmp_path / "ratchet.json"
    ratchet_file.write_text('{"violations": 2}', encoding="utf-8")

    violations = []
    res = check_ratchet(violations, ratchet_file)
    assert res.ok is True
    assert res.delta == -2
    assert res.message == ""


def test_ratchet_hint_message_format(tmp_path: Path):
    ratchet_file = tmp_path / "ratchet.json"
    ratchet_file.write_text('{"violations": 1}', encoding="utf-8")

    violations = [
        Violation(
            contract_id="c1",
            file_path="a.py",
            line_number=10,
            imported_module="mod1",
            forbidden_pattern="mod1",
            reason="reason1",
        ),
        Violation(
            contract_id="c2",
            file_path="b.py",
            line_number=20,
            imported_module="mod2",
            forbidden_pattern="mod2",
            reason="reason2",
        ),
    ]

    res = check_ratchet(violations, ratchet_file)
    assert res.ok is False
    assert "found 2" in res.message
    assert "allowed 1" in res.message
    assert "update-ratchet" in res.message
