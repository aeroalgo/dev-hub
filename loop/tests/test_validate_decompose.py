"""S1 — decompose v1 validator harden: D1/D3/D4/D5/D7 + --strict."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic_yaml import (  # noqa: E402
    back_api_default_skill_paths,
    validate_decompose_full,
    validate_decompose_tree,
    _validate_decompose_skills,
    load_decompose,
)

_VALID_BACK_SKILLS = {
    "code_surface": "api",
    "impl": back_api_default_skill_paths(),
}
_VALID_INTEG_SKILLS = {
    "code_surface": "api",
    "impl": [".agents/skills/modern-python/SKILL.md"],
}


_MINIMAL_DECOMPOSE_INDEX_MD = """\
# decompose-demo

## Requirements coverage
| ID | sNN |
| FR-1 | s01 |

## Stages coverage
| Stage | sNN |
| s01 | s01 |

## Outcome map
| Outcome | sNN |
| ok | s01 |

## Replacement cleanup
n/a — greenfield
"""


def _write_minimal_index_md(dec: Path) -> None:
    (dec / "md").mkdir(parents=True, exist_ok=True)
    (dec / "md" / "decompose-index.md").write_text(_MINIMAL_DECOMPOSE_INDEX_MD, encoding="utf-8")


def _write(p: Path, data: dict) -> Path:
    role = str(data.get("role") or "integ")
    default_skills = _VALID_BACK_SKILLS if role == "back" else _VALID_INTEG_SKILLS
    base = {
        "schema": "epic-decompose/v1",
        "role": "integ",
        "step_id": "e99",
        "plan_id": "x",
        "title": "t",
        "next_phase": "INTEG IMPLEMENT",
        "goal": "g",
        "delta": ["frontend/src/x.ts"],
        "out_of_scope": ["o"],
        "plan_contract": {
            "fr_ids": ["FR-001"],
            "nouns": ["surface"],
            "layout_paths": [],
            "ac_quotes": [],
            "plan_jumps": [],
        },
        "checkpoints": [
            {"id": "cp1", "criterion": "c", "verify": "rg -n 'foo-cp1' src"},
            {"id": "cp2", "criterion": "c2", "verify": "rg -n 'bar-cp2' src"},
        ],
        "skills": dict(default_skills),
    }
    base.update(data)
    if "skills" not in data:
        role2 = str(base.get("role") or "integ")
        base["skills"] = (
            dict(_VALID_BACK_SKILLS) if role2 == "back" else dict(_VALID_INTEG_SKILLS)
        )
    p.write_text(
        yaml.safe_dump(base, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return p


def test_d1_duplicate_global_verify_fails(tmp_path: Path) -> None:
    p = _write(tmp_path / "e99.yaml", {"verify": ["rg -n x src", "rg -n x src"]})
    errors, warnings = validate_decompose_full(p)
    assert any("duplicates another global verify" in e for e in errors)
    assert warnings == []


def test_d7_em_dash_in_cp_verify_fails(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {"checkpoints": [
            {"id": "cp1", "criterion": "c", "verify": ".venv/bin/pytest -q — passed"},
            {"id": "cp2", "criterion": "c2", "verify": "rg -n 'e99:cp2' src"},
        ]},
    )
    errors, _ = validate_decompose_full(p)
    assert any("em-dash" in e for e in errors)


def test_d7_em_dash_in_global_verify_fails(tmp_path: Path) -> None:
    p = _write(tmp_path / "e99.yaml", {"verify": [".venv/bin/pytest -q — passed"]})
    errors, _ = validate_decompose_full(p)
    assert any("em-dash" in e for e in errors)


def test_d5_template_tdd_is_warning_only(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {"tdd": ["<placeholder: fill me>", "real tdd step"]},
    )
    errors, warnings = validate_decompose_full(p)
    assert errors == []
    assert any("tdd" in w and "template" in w for w in warnings)


def test_d4_context_files_not_in_delta_is_warning(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "delta": ["apps/api/main.py: route"],
            "context": {"files": ["apps/api/other.py"]},
        },
    )
    errors, warnings = validate_decompose_full(p)
    assert errors == []
    assert any("context.files" in w for w in warnings)


def test_d4_context_files_mentioned_in_delta_no_warning(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "delta": ["apps/api/other.py: change X"],
            "context": {"files": ["apps/api/other.py"]},
        },
    )
    _errors, warnings = validate_decompose_full(p)
    assert not any("context.files" in w for w in warnings)


def test_d3_cp_equals_global_verify_is_warning(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "verify": ["rg -n 'shared' src"],
            "checkpoints": [
                {"id": "cp1", "criterion": "c", "verify": "rg -n 'shared' src"},
                {"id": "cp2", "criterion": "c2", "verify": "rg -n 'uniq' src"},
            ],
        },
    )
    errors, warnings = validate_decompose_full(p)
    assert errors == []
    assert any("identical to a global verify" in w for w in warnings)


def test_validate_decompose_full_errors_only(tmp_path: Path) -> None:
    # returns errors and warnings; FAIL still surfaces in errors.
    p = _write(tmp_path / "e99.yaml", {"verify": ["a", "a"]})
    errs, _warnings = validate_decompose_full(p)
    assert isinstance(errs, list)
    assert any("duplicates another global verify" in e for e in errs)


def test_clean_shard_no_errors(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "verify": ["rg -n 'global1' src"],
            "checkpoints": [
                {"id": "cp1", "criterion": "c", "verify": "rg -n 'clean-cp1' src"},
                {"id": "cp2", "criterion": "c2", "verify": "rg -n 'clean-cp2' src"},
            ],
        },
    )
    errors, _warnings = validate_decompose_full(p)
    assert errors == []


def test_bin_pytest_is_a_runnable_checkpoint_command(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "checkpoints": [
                {"id": "cp1", "criterion": "c", "verify": "bin/pytest tests/test_foo.py -q"},
                {"id": "cp2", "criterion": "c2", "verify": "bin/pytest tests/test_bar.py -q"},
            ]
        },
    )
    errors, _warnings = validate_decompose_full(p)
    assert errors == []


def test_full_hub_suite_is_forbidden_in_decompose_checkpoint(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "checkpoints": [
                {"id": "cp1", "criterion": "c", "verify": "bin/pytest -q --tb=line"},
                {"id": "cp2", "criterion": "c2", "verify": "rg -n 'scoped' src"},
            ]
        },
    )
    errors, _warnings = validate_decompose_full(p)
    assert any("full pytest suite" in error and "QA" in error for error in errors)


def test_targeted_hub_suite_is_not_classified_as_full(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "e99.yaml",
        {
            "checkpoints": [
                {"id": "cp1", "criterion": "c", "verify": "bin/pytest loop/tests/test_foo.py -q"},
                {"id": "cp2", "criterion": "c2", "verify": "rg -n 'scoped' src"},
            ]
        },
    )
    errors, _warnings = validate_decompose_full(p)
    assert not any("full pytest suite" in error for error in errors)


def test_validate_decompose_tree_rejects_full_hub_suite(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "demo"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(
        dec / "yaml" / "steps" / "s01-ok.yaml",
        {
            "step_id": "s01",
            "plan_id": "demo",
            "role": "back",
            "verify": ["`bin/pytest`"],
        },
    )
    errs = validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml")
    assert errs
    assert any("full suite" in e or "bin/pytest`" in e for e in errs)


def test_validate_decompose_tree_ok_and_fail(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "demo"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n"
        "- id: s02\n"
        "  file: s02-bad.yaml\n"
        "  title: bad\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(dec / "yaml" / "steps" / "s01-ok.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    (dec / "yaml" / "steps" / "s02-bad.yaml").write_text(
        "schema: epic-decompose-shard/v1\n"
        "plan_id: demo\n"
        "step_id: s02\n"
        "title: bad\n"
        "next_phase: BACK IMPLEMENT\n"
        "goal: g\n"
        "delta: [x]\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: c\n"
        "    verify: rg -n x src\n",
        encoding="utf-8",
    )
    errs = validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml")
    assert errs
    assert any("s02" in e for e in errs)

    # only good shard → empty after removing bad from index
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    assert validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml") == []


def test_validate_decompose_tree_requires_index_md_sections(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "demo"
    (dec / "yaml" / "steps").mkdir(parents=True)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "source_md: decompose-index.md\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(dec / "yaml" / "steps" / "s01-ok.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    errs = validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml")
    assert errs
    assert any("decompose-index.md" in e or "index.md" in e for e in errs)

    _write_minimal_index_md(dec)
    assert validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml") == []


def test_validate_decompose_tree_rejects_bare_snn_filename(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "demo"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  title: bad name\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(dec / "yaml" / "steps" / "s01.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    errs = validate_decompose_tree(tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml")
    assert errs
    assert any("s01-<slug>" in e or "s01-" in e for e in errs)


def test_validate_decompose_tree_rejects_short_folder_when_plan_has_slug(
    tmp_path: Path,
) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    (plan_dir / "plan-T-HUB-023-hooks-llm-fallbacks.md").parent.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan-T-HUB-023-hooks-llm-fallbacks.md").write_text("# p\n", encoding="utf-8")
    dec = plan_dir / "T-HUB-023"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-HUB-023\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(
        dec / "yaml" / "steps" / "s01-ok.yaml",
        {"step_id": "s01", "plan_id": "T-HUB-023", "role": "back"},
    )
    errs = validate_decompose_tree(tmp_path, "memory-bank/back/plan/T-HUB-023/yaml/decompose-index.yaml")
    assert errs
    assert any("short queue id" in e or "hooks-llm-fallbacks" in e for e in errs)


def test_resolve_decompose_ref_for_gate_falls_back_to_find_index(tmp_path: Path) -> None:
    from epic_paths import resolve_decompose_ref_for_gate  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "T-030"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-030\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-x.yaml\n"
        "  title: x\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(dec / "yaml" / "steps" / "s01-x.yaml", {"step_id": "s01", "plan_id": "T-030", "role": "back"})
    epic = {
        "armed_step": "DECOMPOSE",
        "armed_epic": "T-030",
        "role": "back",
        "armed_decompose": None,
    }
    ref = resolve_decompose_ref_for_gate(tmp_path, epic)
    assert ref == "memory-bank/back/plan/T-030/yaml/decompose-index.yaml"


def test_load_steps_for_index_prefers_yaml_when_md_coexists(tmp_path: Path) -> None:
    from loop.roadmap_queue import load_steps_for_index

    dec = tmp_path / "memory-bank" / "back" / "plan" / "T-DEMO" / "yaml"
    dec.mkdir(parents=True)
    yaml_file = dec / "decompose-index.yaml"
    yaml_file.write_text(
        """schema: epic-decompose-index/v1
plan_id: T-DEMO
steps:
- id: s01
  file: s01-demo.yaml
  title: demo step from yaml
  next_phase: BACK IMPLEMENT
  status: completed
""",
        encoding="utf-8",
    )
    md_file = yaml_file.with_name("index.md")
    md_file.write_text(
        """| step_id | title | status |
| :--- | :--- | :--- |
| **s01** | demo step from md | pending |
""",
        encoding="utf-8",
    )
    loaded = load_steps_for_index(tmp_path, yaml_file)
    assert loaded["ok"] is True
    assert loaded["source"] == "yaml"
    assert loaded["steps"][0]["title"] == "demo step from yaml"
    assert loaded["steps"][0]["status"] == "completed"


def test_skills_empty_impl_on_api_fails(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s01-x.yaml",
        {
            "role": "back",
            "step_id": "s01",
            "skills": {"code_surface": "api", "impl": []},
        },
    )
    errors, _ = validate_decompose_full(p)
    assert any("empty on code_surface" in e or "skills.impl" in e for e in errors)


def test_skills_core_partial_fails(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s01-x.yaml",
        {
            "role": "back",
            "step_id": "s01",
            "skills": {
                "code_surface": "api",
                "impl": [
                    ".agents/skills/tdd/SKILL.md",
                    ".agents/skills/fastapi-templates/SKILL.md",
                    ".agents/skills/async-python-patterns/SKILL.md",
                    ".agents/skills/python-error-handling/SKILL.md",
                ],
            },
        },
    )
    errors, _ = validate_decompose_full(p)
    assert any("Core(4) incomplete" in e for e in errors)


def test_skills_situational_omit_justification_ok(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s01-x.yaml",
        {
            "role": "back",
            "step_id": "s01",
            "skills": {
                "code_surface": "api",
                "impl": [
                    ".agents/skills/tdd/SKILL.md",
                    ".agents/skills/python-testing-patterns/SKILL.md",
                    ".agents/skills/modern-python/SKILL.md",
                    ".agents/skills/python-anti-patterns/SKILL.md",
                    ".agents/skills/async-python-patterns/SKILL.md",
                    ".agents/skills/python-error-handling/SKILL.md",
                ],
                "omit_justification": {
                    "fastapi-templates": "no HTTP routes; service-only step",
                },
            },
        },
    )
    errors, _ = validate_decompose_full(p)
    assert not any("fastapi-templates" in e and "missing default" in e for e in errors)
    assert not any("Core(4)" in e for e in errors)


def test_skills_docs_empty_impl_ok(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "s01-x.yaml",
        {
            "role": "back",
            "step_id": "s01",
            "skills": {"code_surface": "docs", "impl": []},
        },
    )
    errors, _ = validate_decompose_full(p)
    assert not any("skills" in e for e in errors)


def test_validate_decompose_tree_rejects_empty_skills(tmp_path: Path) -> None:
    dec = tmp_path / "memory-bank" / "back" / "plan" / "demo"
    (dec / "yaml" / "steps").mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "yaml" / "decompose-index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(
        dec / "yaml" / "steps" / "s01-ok.yaml",
        {
            "step_id": "s01",
            "plan_id": "demo",
            "role": "back",
            "skills": {"code_surface": "api", "impl": []},
        },
    )
    errs = validate_decompose_tree(
        tmp_path, "memory-bank/back/plan/demo/yaml/decompose-index.yaml"
    )
    assert errs
    assert any("skills" in e for e in errs)
