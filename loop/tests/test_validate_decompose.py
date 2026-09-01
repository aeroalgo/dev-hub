"""S1 — decompose v1 validator harden: D1/D3/D4/D5/D7 + --strict."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic_yaml import validate_decompose_full, validate_decompose_yaml  # noqa: E402

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
    (dec / "index.md").write_text(_MINIMAL_DECOMPOSE_INDEX_MD, encoding="utf-8")


def _write(p: Path, data: dict) -> Path:
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
        "checkpoints": [
            {"id": "cp1", "criterion": "c", "verify": "rg -n 'foo-cp1' src"},
            {"id": "cp2", "criterion": "c2", "verify": "rg -n 'bar-cp2' src"},
        ],
    }
    base.update(data)
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


def test_back_compat_validate_decompose_yaml_errors_only(tmp_path: Path) -> None:
    # returns only errors list (no warnings); FAIL still surfaces.
    p = _write(tmp_path / "e99.yaml", {"verify": ["a", "a"]})
    errs = validate_decompose_yaml(p)
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


def test_strict_via_cli_promotes_warnings(tmp_path: Path) -> None:
    import subprocess

    p = _write(tmp_path / "e99.yaml", {"tdd": ["<placeholder>"]})
    cwd = str(tmp_path)
    # default: ok (warnings only)
    r_default = subprocess.run(
        [sys.executable, str(_HOOKS / "epic_resolve.py"), "validate-step",
         "--path", str(p.relative_to(tmp_path))],
        capture_output=True, text=True, cwd=cwd,
    )
    import json
    d_default = json.loads(r_default.stdout)
    assert d_default["ok"] is True
    assert len(d_default["warnings"]) >= 1

    # --strict: warnings promoted to errors → exit 2
    r_strict = subprocess.run(
        [sys.executable, str(_HOOKS / "epic_resolve.py"), "validate-step",
         "--path", str(p.relative_to(tmp_path)), "--strict"],
        capture_output=True, text=True, cwd=cwd,
    )
    d_strict = json.loads(r_strict.stdout)
    assert r_strict.returncode == 2
    assert d_strict["ok"] is False
    assert len(d_strict["errors"]) >= 1


def test_invented_shard_schema_rejected(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_yaml  # noqa: E402

    p = tmp_path / "s03-bad.yaml"
    p.write_text(
        "schema: epic-decompose-shard/v1\n"
        "plan_id: demo\n"
        "step_id: s03\n"
        "title: t\n"
        "next_phase: BACK IMPLEMENT\n"
        "as_built:\n"
        "  as_is: [x]\n"
        "  delta: [y]\n"
        "checkpoints:\n"
        "  - id: cp1\n"
        "    criterion: c\n"
        "    verify: rg -n foo src\n",
        encoding="utf-8",
    )
    errs = validate_decompose_yaml(p)
    assert errs
    blob = " ".join(errs)
    assert "epic-decompose/v1" in blob
    assert "epic-decompose-shard/v1" in blob or "FORBIDDEN" in blob or "must be" in blob


def test_as_built_dict_rejected(tmp_path: Path) -> None:
    p = tmp_path / "s03-dict.yaml"
    data = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s03",
        "plan_id": "demo",
        "title": "t",
        "next_phase": "BACK IMPLEMENT",
        "goal": "g",
        "as_built": {"as_is": ["a"], "delta": ["b"]},
        "delta": ["edit x"],
        "out_of_scope": ["o"],
        "checkpoints": [
            {"id": "cp1", "criterion": "c", "verify": "rg -n a src"},
            {"id": "cp2", "criterion": "c2", "verify": "rg -n b src"},
        ],
    }
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    errors, _ = validate_decompose_full(p)
    assert errors
    assert any("as_built" in e or "list" in e.lower() or "invalid" in e for e in errors)


def test_validate_decompose_tree_ok_and_fail(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "decompose-demo"
    dec.mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "index.yaml").write_text(
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
    _write(dec / "s01-ok.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    (dec / "s02-bad.yaml").write_text(
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
    errs = validate_decompose_tree(tmp_path, "decompose-demo")
    assert errs
    assert any("s02" in e for e in errs)

    # only good shard → empty after removing bad from index
    (dec / "index.yaml").write_text(
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
    assert validate_decompose_tree(tmp_path, str(dec)) == []


def test_validate_decompose_tree_requires_index_md_sections(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "decompose-demo"
    dec.mkdir(parents=True)
    (dec / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "source_md: index.md\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01-ok.yaml\n"
        "  title: ok\n"
        "  next_phase: BACK IMPLEMENT\n"
        "  status: pending\n",
        encoding="utf-8",
    )
    _write(dec / "s01-ok.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    errs = validate_decompose_tree(tmp_path, str(dec))
    assert errs
    assert any("index.md" in e for e in errs)

    _write_minimal_index_md(dec)
    assert validate_decompose_tree(tmp_path, str(dec)) == []


def test_validate_decompose_tree_rejects_bare_snn_filename(tmp_path: Path) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "decompose-demo"
    dec.mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "index.yaml").write_text(
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
    _write(dec / "s01.yaml", {"step_id": "s01", "plan_id": "demo", "role": "back"})
    errs = validate_decompose_tree(tmp_path, str(dec))
    assert errs
    assert any("s01-<slug>" in e or "s01-" in e for e in errs)


def test_validate_decompose_tree_rejects_short_folder_when_plan_has_slug(
    tmp_path: Path,
) -> None:
    from epic_yaml import validate_decompose_tree  # noqa: E402

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-023-hooks-llm-fallbacks.md").write_text("# p\n", encoding="utf-8")
    dec = plan_dir / "decompose-T-HUB-023"
    dec.mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "index.yaml").write_text(
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
        dec / "s01-ok.yaml",
        {"step_id": "s01", "plan_id": "T-HUB-023", "role": "back"},
    )
    errs = validate_decompose_tree(tmp_path, str(dec))
    assert errs
    assert any("short queue id" in e or "hooks-llm-fallbacks" in e for e in errs)


def test_resolve_decompose_ref_for_gate_falls_back_to_find_index(tmp_path: Path) -> None:
    from epic_paths import resolve_decompose_ref_for_gate  # noqa: E402

    dec = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-030"
    dec.mkdir(parents=True)
    _write_minimal_index_md(dec)
    (dec / "index.yaml").write_text(
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
    _write(dec / "s01-x.yaml", {"step_id": "s01", "plan_id": "T-030", "role": "back"})
    epic = {
        "armed_step": "DECOMPOSE",
        "armed_epic": "T-030",
        "role": "back",
        "armed_decompose": None,
    }
    ref = resolve_decompose_ref_for_gate(tmp_path, epic)
    assert ref == "memory-bank/back/plan/decompose-T-030/index.yaml"
