import pytest
from pathlib import Path
import yaml

from loop.mb_scaffold.scaffold_decompose import (
    scaffold_decompose,
    DecomposeOutline,
    OutlineStep,
    OutlineRequirement,
)
from loop.paths.epic_layout import resolve, EpicLayoutKind
from epic.traceability import parse_plan_requirements, parse_decompose_refs, run_checks


def test_scaffold_decompose_5steps(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    reqs = [OutlineRequirement(id=f"FR-00{i}", text=f"Req {i}") for i in range(1, 6)]
    steps = [
        OutlineStep(step_id=f"s0{i}", title=f"Step {i} title", maps_to=[f"FR-00{i}"])
        for i in range(1, 6)
    ]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=reqs,
        outline_steps=steps,
    )

    res = scaffold_decompose(epic_id=epic_id, role=role, outline=outline, project_root=tmp_path)
    assert res.ok
    assert len(res.created) == 7  # 5 steps + index.yaml + index.md

    idx_yaml = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    assert idx_yaml.exists()
    idx_data = yaml.safe_load(idx_yaml.read_text())
    assert idx_data["schema"] == "epic-decompose-index/v1"
    assert len(idx_data["steps"]) == 5

    idx_md = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_INDEX_MD, project_root=tmp_path)
    assert idx_md.exists()
    md_text = idx_md.read_text()
    assert "## Requirements coverage" in md_text
    assert "## Stages coverage" in md_text
    assert "## Outcome map" in md_text
    assert "## Replacement cleanup" in md_text

    for i in range(1, 6):
        step_path = resolve(
            role=role,
            epic_id=epic_id,
            kind=EpicLayoutKind.DECOMPOSE_STEP,
            step_id=f"s0{i}",
            step_slug=f"step-{i}-title",
            project_root=tmp_path,
        )
        assert step_path.exists()
        step_data = yaml.safe_load(step_path.read_text())
        assert step_data["schema"] == "epic-decompose/v1"
        assert step_data["step_id"] == f"s0{i}"
        assert step_data["plan_id"] == epic_id
        assert step_data["plan_contract"]["fr_ids"] == [f"FR-00{i}"]


def test_guard_no_overwrite(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    reqs = [OutlineRequirement(id="FR-001", text="Req 1")]
    steps = [OutlineStep(step_id="s01", title="Step 1 title", maps_to=["FR-001"])]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=reqs,
        outline_steps=steps,
    )

    scaffold_decompose(epic_id=epic_id, role=role, outline=outline, project_root=tmp_path)

    step_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s01",
        step_slug="step-1-title",
        project_root=tmp_path,
    )
    step_data = yaml.safe_load(step_path.read_text())
    step_data["goal"] = "User edited goal"
    step_path.write_text(yaml.dump(step_data))

    with pytest.raises(ValueError, match="non-empty goal"):
        scaffold_decompose(epic_id=epic_id, role=role, outline=outline, force=False, project_root=tmp_path)

    res = scaffold_decompose(epic_id=epic_id, role=role, outline=outline, force=True, project_root=tmp_path)
    assert res.ok


def test_formula_merge(tmp_path: Path):
    epic_id = "T-HUB-047-test"
    role = "back"
    steps = [
        OutlineStep(step_id="s01", title="Initial title 1", maps_to=["FR-001"]),
        OutlineStep(step_id="s02", title="Initial title 2", maps_to=["FR-002"]),
    ]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=[],
        outline_steps=steps,
    )

    res = scaffold_decompose(
        epic_id=epic_id,
        role=role,
        outline=outline,
        formula_id="hooks-epic",
        project_root=tmp_path,
    )
    assert res.ok

    s01_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s01",
        step_slug="env-contract",
        project_root=tmp_path,
    )
    assert s01_path.exists()
    s01_data = yaml.safe_load(s01_path.read_text())
    assert s01_data["title"] == "env-contract"

    s02_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s02",
        step_slug="unified-llm-models",
        project_root=tmp_path,
    )
    assert s02_path.exists()
    s02_data = yaml.safe_load(s02_path.read_text())
    assert s02_data["title"] == "unified-llm-models"

    assert len(res.created) == 10  # 2 index files + 8 step files


def test_agent_add_snn(tmp_path: Path):
    """Verify that adding an extra step beyond outline floor works smoothly."""
    epic_id = "T-HUB-047-test"
    role = "back"
    steps = [
        OutlineStep(step_id="s01", title="Step 1", maps_to=["FR-001"]),
    ]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=[OutlineRequirement(id="FR-001", text="Req 1")],
        outline_steps=steps,
    )
    scaffold_decompose(epic_id=epic_id, role=role, outline=outline, project_root=tmp_path)

    s02_path = resolve(
        role=role,
        epic_id=epic_id,
        kind=EpicLayoutKind.DECOMPOSE_STEP,
        step_id="s02",
        step_slug="extra-work",
        project_root=tmp_path,
    )
    s02_path.write_text(
        f"schema: epic-decompose/v1\n"
        f"role: {role}\n"
        f"step_id: s02\n"
        f"plan_id: {epic_id}\n"
        f"title: Extra Work\n"
        f"plan_contract:\n"
        f"  fr_ids: [FR-001]\n",
        encoding="utf-8",
    )
    assert s02_path.exists()


def test_validate_traceability_still_green(tmp_path: Path):
    """Scaffolded 3-step decompose validates cleanly via traceability checks against plan.md."""
    epic_id = "T-HUB-047-test"
    role = "back"
    reqs = [OutlineRequirement(id=f"FR-00{i}", text=f"Req {i}") for i in range(1, 4)]
    steps = [
        OutlineStep(step_id=f"s0{i}", title=f"Step {i}", maps_to=[f"FR-00{i}"])
        for i in range(1, 4)
    ]
    outline = DecomposeOutline(
        title="Test Epic",
        requirements=reqs,
        outline_steps=steps,
    )

    plan_md_path = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    plan_md_path.parent.mkdir(parents=True, exist_ok=True)
    plan_md_path.write_text(
        "# Plan Test Epic\n\n"
        "## Requirements\n\n"
        "FR-001 Req 1\n"
        "FR-002 Req 2\n"
        "FR-003 Req 3\n",
        encoding="utf-8",
    )

    scaffold_decompose(epic_id=epic_id, role=role, outline=outline, project_root=tmp_path)

    plan_reqs = parse_plan_requirements(plan_md_path)
    decomp_index_yaml = resolve(role=role, epic_id=epic_id, kind=EpicLayoutKind.DECOMPOSE_INDEX_YAML, project_root=tmp_path)
    decomp_refs = parse_decompose_refs(decomp_index_yaml.parent)

    findings = run_checks(plan_reqs, decomp_refs, impl_ev={}, strict=False)
    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    assert len(critical_findings) == 0
