"""S4 — parity: every shard kind gives meaningful FAIL via validate-step."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _validate(rel: str, data: dict, tmp_path: Path, *, parent: str) -> tuple[int, dict]:
    d = tmp_path / parent
    d.mkdir(parents=True, exist_ok=True)
    p = d / Path(rel).name
    p.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    rel_path = str(p.relative_to(tmp_path))
    r = subprocess.run(
        [sys.executable, str(_HOOKS / "epic_resolve.py"), "validate-step",
         "--path", rel_path],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        return r.returncode, {"_raw": r.stdout, "_err": r.stderr}


def _security_doc(**over) -> dict:
    base = {
        "schema": "epic-security/v1",
        "role": "back",
        "step_id": "a01",
        "plan_id": "x",
        "title": "t",
        "status": "completed",
        "date": "2026-08-02",
        "audit_surface": "auth module",
        "evidence_commands": [".venv/bin/pytest -q"],
        "findings": [{"id": "F1", "severity": "low", "path": "a.py", "note": "ok"}],
        "checkpoints": [{"id": "cp1", "criterion": "c", "status": "done"}],
    }
    base.update(over)
    return base


def _refactor_doc(**over) -> dict:
    base = {
        "schema": "epic-refactor/v1",
        "role": "back",
        "step_id": "r01",
        "plan_id": "x",
        "title": "t",
        "status": "completed",
        "date": "2026-08-02",
        "behavior_freeze": "behavior preserved",
        "done": ["refactored X"],
        "files": ["apps/api/x.py"],
        "tests": ["`timeout 300s .venv/bin/pytest -q`"],
        "checkpoints": [{"id": "cp1", "criterion": "c", "status": "done"}],
    }
    base.update(over)
    return base


def _implement_doc(**over) -> dict:
    base = {
        "schema": "epic-implement/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": "x",
        "title": "t",
        "status": "completed",
        "implement_index": "idx",
        "date": "2026-08-02",
        "done": ["done X"],
        "files": ["apps/api/x.py"],
        "integration_check": ["integ ok"],
        "tests": [".venv/bin/pytest -q"],
        "checkpoints": [{"id": "cp1", "criterion": "c", "status": "done"}],
    }
    base.update(over)
    return base


def _qa_doc(**over) -> dict:
    base = {
        "schema": "epic-qa/v1",
        "role": "back",
        "date": "2026-08-02",
        "reviewer": "r",
        "verdict": "pass",
        "scope": ["apps/api/x.py"],
        "checks": ["pytest green"],
    }
    base.update(over)
    return base


# --- security: em-dash / dup in evidence_commands ---

def test_security_em_dash_evidence_fails(tmp_path: Path) -> None:
    rc, rep = _validate(
        "a01-sec.yaml",
        _security_doc(evidence_commands=[".venv/bin/pytest -q — passed"]),
        tmp_path, parent="memory-bank/back/security/implement/implement-x",
    )
    assert rc == 2
    assert any("em-dash" in e for e in rep["errors"])


def test_security_dup_evidence_fails(tmp_path: Path) -> None:
    rc, rep = _validate(
        "a01-sec.yaml",
        _security_doc(evidence_commands=["rg -n x src", "rg -n x src"]),
        tmp_path, parent="memory-bank/back/security/implement/implement-x",
    )
    assert rc == 2
    assert any("duplicates another evidence_command" in e for e in rep["errors"])


def test_security_clean_passes(tmp_path: Path) -> None:
    rc, rep = _validate(
        "a01-sec.yaml",
        _security_doc(),
        tmp_path, parent="memory-bank/back/security/implement/implement-x",
    )
    assert rc == 0, rep


# --- refactor: em-dash in tests ---

def test_refactor_em_dash_tests_fails(tmp_path: Path) -> None:
    rc, rep = _validate(
        "r01-ref.yaml",
        _refactor_doc(tests=[".venv/bin/pytest -q — passed"]),
        tmp_path, parent="memory-bank/back/refactor/implement/implement-x",
    )
    assert rc == 2
    assert any(e for e in rep["errors"])


def test_refactor_clean_passes(tmp_path: Path) -> None:
    rc, rep = _validate(
        "r01-ref.yaml",
        _refactor_doc(),
        tmp_path, parent="memory-bank/back/refactor/implement/implement-x",
    )
    assert rc == 0, rep


# --- implement: em-dash in tests ---

def test_implement_em_dash_tests_fails(tmp_path: Path) -> None:
    rc, rep = _validate(
        "s01-impl.yaml",
        _implement_doc(tests=[".venv/bin/pytest -q — passed"]),
        tmp_path, parent="memory-bank/back/implement/implement-x",
    )
    assert rc == 2
    assert rep["ok"] is False


# --- qa: meaningful FAIL (missing scope) ---

def test_qa_missing_scope_fails(tmp_path: Path) -> None:
    rc, rep = _validate(
        "qa-20260802-x.yaml",
        _qa_doc(scope=[]),
        tmp_path, parent="memory-bank/back/qa/qa-20260802",
    )
    assert rc == 2
    assert any("scope" in e for e in rep["errors"])


def test_qa_clean_passes(tmp_path: Path) -> None:
    rc, rep = _validate(
        "qa-20260802-x.yaml",
        _qa_doc(),
        tmp_path, parent="memory-bank/back/qa/qa-20260802",
    )
    assert rc == 0, rep
