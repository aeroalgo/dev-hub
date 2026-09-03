import pytest
from pathlib import Path
from loop.paths.epic_layout import resolve, EpicLayoutKind


def test_resolve_plan_md():
    p = resolve("back", "T-HUB-047-test", "plan_md")
    assert str(p).endswith("memory-bank/back/plan/T-HUB-047-test/md/plan.md")


def test_resolve_plan_yaml():
    p = resolve("back", "T-HUB-047-test", "plan_yaml")
    assert str(p).endswith("memory-bank/back/plan/T-HUB-047-test/yaml/plan.yaml")


def test_resolve_decompose_index():
    md_p = resolve("back", "T-HUB-047-test", "decompose_index_md")
    yaml_p = resolve("back", "T-HUB-047-test", "decompose_index_yaml")
    assert str(md_p).endswith("memory-bank/back/plan/T-HUB-047-test/md/decompose-index.md")
    assert str(yaml_p).endswith("memory-bank/back/plan/T-HUB-047-test/yaml/decompose-index.yaml")


def test_resolve_decompose_step():
    p = resolve("back", "T-HUB-047-test", "decompose_step", "s03")
    assert str(p).endswith("memory-bank/back/plan/T-HUB-047-test/yaml/steps/s03.yaml")

    p_slug = resolve("back", "T-HUB-047-test", "decompose_step", "s03", step_slug="my-step")
    assert str(p_slug).endswith("memory-bank/back/plan/T-HUB-047-test/yaml/steps/s03-my-step.yaml")


def test_resolve_implement_step():
    p = resolve("back", "T-HUB-047-test", "implement_step", "s03")
    assert str(p).endswith("memory-bank/back/implement/T-HUB-047-test/yaml/steps/s03.yaml")


def test_resolve_phase_yamls():
    qa = resolve("back", "T-HUB-047-test", "qa_yaml")
    assert str(qa).endswith("memory-bank/back/qa/T-HUB-047-test/yaml/qa.yaml")

    analyze = resolve("back", "T-HUB-047-test", "analyze_yaml")
    assert str(analyze).endswith("memory-bank/back/analyze/T-HUB-047-test/yaml/analyze.yaml")

    audit = resolve("back", "T-HUB-047-test", "audit_yaml")
    assert str(audit).endswith("memory-bank/back/audit/T-HUB-047-test/yaml/audit.yaml")


def test_resolve_unknown_kind():
    with pytest.raises(ValueError):
        resolve("back", "T-HUB-047-test", "unknown_kind")


def test_resolve_missing_step_id():
    with pytest.raises(ValueError):
        resolve("back", "T-HUB-047-test", "decompose_step")


def test_resolve_custom_root(tmp_path):
    p = resolve("back", "T-HUB-047-test", "plan_md", project_root=tmp_path)
    assert p == tmp_path / "memory-bank/back/plan/T-HUB-047-test/md/plan.md"
