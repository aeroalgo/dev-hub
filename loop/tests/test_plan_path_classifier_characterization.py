"""Characterization and behavior freeze oracle test matrix for plan path classifiers and board_sync path helpers.

Step: s01 of T-HUB-104-plan-path-classifier-dedup.
"""
from pathlib import Path
import pytest

from loop.mb_load.plan_section import is_whole_plan_path
from loop.mb_load.plan_section import is_markdown_plan_path
from loop.board_sync._epic_paths import (
    epic_id_from_plan_path as resolver_epic_id_from_plan_path,
    find_decompose_index_path as resolver_find_decompose,
    plan_path as resolver_plan_path,
)

scan_gates_plan_path = resolver_plan_path
scan_gates_find_decompose = resolver_find_decompose


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("memory-bank/back/plan/T-HUB-001/md/plan.md", True),
        ("memory-bank/back/plan/T-HUB-001/plan.md", True),
        ("memory-bank/back/plan/plan-T-HUB-001.md", True),
        ("md/plan.md", True),
        ("plan.md", True),
        ("plan-feature.md", True),
        ("plan-.md", False),
        ("some/nested/md/plan.md", True),
        ("some/nested/plan-test.md", True),
        ("some\\nested\\md\\plan.md", True),
        ("some\\nested\\plan-test.md", True),
        ("memory-bank/back/plan/T-HUB-001/yaml/decompose-index.yaml", False),
        ("memory-bank/back/plan/T-HUB-001/yaml/steps/s01.yaml", False),
        ("memory-bank/back/gap/gap-001.md", False),
        ("gap-001.md", False),
        ("memory-bank/back/analyze/analyze-001.md", False),
        ("analyze-001.md", False),
        ("memory-bank/back/plan/T-HUB-001/md/decompose-index.md", False),
        ("decompose-index.md", False),
        ("memory-bank/activeContext.md", False),
        ("random_file.py", False),
        ("plan_section.py", False),
        ("plan.json", False),
    ],
)
def test_is_whole_plan_path_characterization(path: str, expected: bool) -> None:
    """Verify is_whole_plan_path behavior baseline."""
    assert is_whole_plan_path(path) is expected
    assert is_whole_plan_path(Path(path)) is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("memory-bank/back/plan/T-HUB-001/md/plan.md", True),
        ("md/plan.md", True),
        ("some/path/md/plan.md", True),
        ("plan-feature.md", True),
        ("memory-bank/back/plan/plan-T-HUB-001.md", True),
        ("gap-001.md", True),
        ("memory-bank/back/gap/gap-001.md", True),
        ("analyze-001.md", True),
        ("memory-bank/back/analyze/analyze-001.md", True),
        ("decompose-index.md", True),
        ("memory-bank/back/plan/T-HUB-001/md/decompose-index.md", True),
        ("plan.md", False),
        ("memory-bank/back/plan/T-HUB-001/plan.md", False),
        ("memory-bank/back/plan/T-HUB-001/yaml/decompose-index.yaml", False),
        ("memory-bank/back/plan/T-HUB-001/yaml/steps/s01.yaml", False),
        ("memory-bank/activeContext.md", False),
        ("random_file.py", False),
        ("plan_section.py", False),
        ("plan.json", False),
        ("gap.yaml", False),
        ("analyze.json", False),
        ("gap-001.MD", False),
        ("GAP-001.md", False),
        ("ANALYZE-001.md", False),
        ("DECOMPOSE-INDEX.md", False),
        ("foo_gap-001.md", False),
        ("gap-.md", True),
        ("analyze-.md", True),
    ],
)
def test_is_markdown_plan_path_characterization(path: str, expected: bool) -> None:
    """Verify is_markdown_plan_path behavior baseline."""
    assert is_markdown_plan_path(path) is expected
    assert is_markdown_plan_path(Path(path)) is expected


def test_board_sync_path_helpers_characterization(tmp_path: Path) -> None:
    """Verify resolver and scan_gates _plan_path / _find_decompose / _epic_id_from_plan_path freeze behavior."""
    project = tmp_path / "repo"
    project.mkdir()

    plan_dir = project / "memory-bank" / "back" / "plan" / "T-HUB-001" / "md"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / "plan.md"
    plan_file.write_text("# Plan", encoding="utf-8")

    yaml_dir = project / "memory-bank" / "back" / "plan" / "T-HUB-001" / "yaml"
    yaml_dir.mkdir(parents=True)
    decomp_file = yaml_dir / "decompose-index.yaml"
    decomp_file.write_text("steps: []", encoding="utf-8")

    # Both _plan_path implementations must return the exact same Path
    res_plan = resolver_plan_path(project, "back", "T-HUB-001")
    scan_plan = scan_gates_plan_path(project, "back", "T-HUB-001")
    assert res_plan == plan_file
    assert scan_plan == plan_file

    # Both _find_decompose implementations must return the exact same Path
    res_decomp = resolver_find_decompose(project, "back", "T-HUB-001")
    scan_decomp = scan_gates_find_decompose(project, "back", "T-HUB-001")
    assert res_decomp == decomp_file
    assert scan_decomp == decomp_file

    # _epic_id_from_plan_path behavior
    assert resolver_epic_id_from_plan_path(plan_file) == "T-HUB-001"
    assert resolver_epic_id_from_plan_path(None) is None

    # Missing epic checks
    assert resolver_plan_path(project, "back", "T-HUB-NONEXISTENT") is None
    assert scan_gates_plan_path(project, "back", "T-HUB-NONEXISTENT") is None
    assert resolver_find_decompose(project, "back", "T-HUB-NONEXISTENT") is None
    assert scan_gates_find_decompose(project, "back", "T-HUB-NONEXISTENT") is None
