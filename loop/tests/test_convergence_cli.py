import json
import sys
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import epic_resolve


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        sys.argv = ["epic_resolve.py", "analyze-convergence", "--help"]
        epic_resolve.main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "analyze-convergence" in captured.out or "analyze-convergence" in captured.err


def test_json_output(tmp_path: Path, capsys):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("Requirement FR-001", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-TEST\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: [FR-001]\n", encoding="utf-8")

    sys.argv = [
        "epic_resolve.py",
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-TEST",
        "--format",
        "json",
    ]
    exit_code = epic_resolve.main()
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["schema"] == "convergence-report/v1"
    assert data["plan_id"] == "T-HUB-TEST"
    assert "findings" in data


def test_text_output(tmp_path: Path, capsys):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("Requirement FR-999 is uncovered", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-TEST\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: []\n", encoding="utf-8")

    sys.argv = [
        "epic_resolve.py",
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-TEST",
        "--format",
        "text",
    ]
    exit_code = epic_resolve.main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "CONVERGENCE REPORT" in captured.out or "findings" in captured.out.lower() or "critical" in captured.out.lower()


def test_exit_codes(tmp_path: Path):
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    decomp_dir = plan_dir / "decompose-T-HUB-TEST"
    decomp_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-TEST.md").write_text("Requirement FR-999 is uncovered", encoding="utf-8")
    (decomp_dir / "index.yaml").write_text("plan_id: T-HUB-TEST\nsteps:\n  - id: s01\n    file: s01.yaml\n", encoding="utf-8")
    (decomp_dir / "s01.yaml").write_text("step_id: s01\nplan_refs: []\n", encoding="utf-8")

    # Without strict -> exit 0
    sys.argv = [
        "epic_resolve.py",
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-TEST",
        "--format",
        "json",
    ]
    assert epic_resolve.main() == 0

    # With strict and CRITICAL/HIGH findings -> exit 1
    sys.argv = [
        "epic_resolve.py",
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--plan-id",
        "T-HUB-TEST",
        "--format",
        "json",
        "--strict",
    ]
    assert epic_resolve.main() == 1


def test_plan_id_optional(tmp_path: Path, capsys):
    sys.argv = [
        "epic_resolve.py",
        "--cwd",
        str(tmp_path),
        "analyze-convergence",
        "--format",
        "json",
    ]
    exit_code = epic_resolve.main()
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["schema"] == "convergence-report/v1"
