"""S1 — decompose v1 validator harden: D1/D3/D4/D5/D7 + --strict."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from epic_yaml import validate_decompose_full, validate_decompose_yaml  # noqa: E402


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
