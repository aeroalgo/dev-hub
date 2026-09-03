"""Smoke test for resolver in loop hot paths (SC-001)."""

from pathlib import Path
from loop.paths.epic_layout import resolve, discover_v2_epics, EpicLayoutKind
from loop.context_loop import discover_decompose_indexes


def test_resolver_loop_smoke(tmp_path: Path):
    role = "back"
    epic_id = "T-SMOKE-002"

    # Setup v2 layout
    decomp_md = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    decomp_md.parent.mkdir(parents=True, exist_ok=True)
    decomp_md.write_text("# Decompose Index\n", encoding="utf-8")

    decomp_yaml = resolve(role, epic_id, EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_yaml.parent.mkdir(parents=True, exist_ok=True)
    decomp_yaml.write_text("schema: epic-decompose-index/v1\nplan_id: T-SMOKE-002\n", encoding="utf-8")

    # Verify discovery
    epics = discover_v2_epics(tmp_path)
    assert (role, epic_id) in epics

    # Verify context_loop discovery
    indexes = discover_decompose_indexes(tmp_path)
    expected_rel = decomp_md.relative_to(tmp_path).as_posix()
    assert expected_rel in indexes
