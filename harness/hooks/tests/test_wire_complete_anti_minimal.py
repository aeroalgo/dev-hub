"""Anti-minimal wire_complete / wire_complete_required machine gates."""

from __future__ import annotations

from pathlib import Path

import yaml

from harness.hooks.epic_yaml import (
    WireCompleteBlock,
    boundary_step_hint,
    implement_load_state,
    validate_decompose_full,
    validate_implement_yaml,
    wire_complete_errors,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _base_decompose(**extra) -> dict:
    doc = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s04",
        "plan_id": "T-HUB-TEST",
        "title": "Ordinary step",
        "next_phase": "BACK IMPLEMENT",
        "goal": "Ship an ordinary outcome",
        "delta": ["touch app/x.py"],
        "checkpoints": [
            {"id": "cp1", "criterion": "ok", "verify": "bin/pytest tests/test_x.py -q"}
        ],
    }
    doc.update(extra)
    return doc


def _base_implement(**extra) -> dict:
    doc = {
        "schema": "epic-implement/v1",
        "role": "back",
        "step_id": "s04",
        "plan_id": "T-HUB-TEST",
        "title": "Ordinary step",
        "status": "in_progress",
        "date": "2026-09-11",
        "done": ["did"],
        "files": ["app/x.py"],
        "integration_check": ["ok"],
        "tests": ["`bin/pytest tests/test_x.py -q` — PASS"],
        "checkpoints": [{"id": "cp1", "criterion": "ok", "status": "done"}],
    }
    doc.update(extra)
    return doc


def test_wire_complete_errors_require_deny_old():
    assert wire_complete_errors(None)
    incomplete = WireCompleteBlock(
        call_sites=["a"],
        enforce_path="t",
        dual_path_rg="rg old",
        instruction_rg="rg teach",
        deny_old_proven=False,
    )
    errs = wire_complete_errors(incomplete, require_deny_old=True)
    assert any("deny_old_proven" in e for e in errs)
    # Legacy blocks without deny flag still pass structural checks when not required.
    assert wire_complete_errors(incomplete, require_deny_old=False) == []
    complete = WireCompleteBlock(
        call_sites=["loop.x"],
        enforce_path="bin/pytest t -q",
        dual_path_rg="rg legacy",
        instruction_rg="rg old-format",
        deny_old_proven=True,
    )
    assert wire_complete_errors(complete, require_deny_old=True) == []


def test_boundary_step_hint_detects_purge_and_enforce():
    assert boundary_step_hint("s06-legacy-fallback-purge")
    assert boundary_step_hint("s04-enforce-verifier-receipt")
    assert not boundary_step_hint("s01-contracts-and-characterization", "Contracts")


def test_decompose_warns_boundary_without_flag(tmp_path: Path):
    path = tmp_path / "s06-legacy-fallback-purge.yaml"
    _write_yaml(
        path,
        _base_decompose(
            step_id="s06",
            title="legacy-fallback-purge leftovers",
            wire_complete_required=False,
        ),
    )
    errors, warnings = validate_decompose_full(path)
    assert errors == []
    assert any("wire_complete_required" in w for w in warnings)


def test_decompose_requires_negative_verify_when_flagged(tmp_path: Path):
    path = tmp_path / "s04-enforce.yaml"
    _write_yaml(
        path,
        _base_decompose(
            step_id="s04",
            title="enforce verifier",
            wire_complete_required=True,
            checkpoints=[
                {"id": "cp1", "criterion": "happy", "verify": "bin/pytest tests/test_x.py -q"}
            ],
        ),
    )
    errors, _warnings = validate_decompose_full(path)
    assert any("wire_complete_required" in e and "negative" in e for e in errors)

    _write_yaml(
        path,
        _base_decompose(
            step_id="s04",
            title="enforce verifier",
            wire_complete_required=True,
            checkpoints=[
                {
                    "id": "cp1",
                    "criterion": "deny old",
                    "verify": "rg legacy_symbol loop/ | expect 0 hits",
                }
            ],
        ),
    )
    errors2, _ = validate_decompose_full(path)
    assert not any("wire_complete_required" in e for e in errors2)


def test_implement_finish_fails_without_wire_complete_when_required(tmp_path: Path):
    root = tmp_path
    dec = root / "memory-bank/back/plan/T-HUB-TEST/yaml/steps/s04-enforce-x.yaml"
    impl = root / "memory-bank/back/implement/T-HUB-TEST/s04-enforce-x.yaml"
    _write_yaml(
        dec,
        _base_decompose(
            step_id="s04",
            title="enforce x",
            wire_complete_required=True,
            checkpoints=[
                {
                    "id": "cp1",
                    "criterion": "deny",
                    "verify": "rg old_path loop/",
                }
            ],
        ),
    )
    _write_yaml(
        impl,
        _base_implement(
            step_id="s04",
            title="enforce x",
            status="in_progress",
            decompose_ref=str(dec.relative_to(root)),
        ),
    )
    errors = validate_implement_yaml(impl, finish=True, cwd=root)
    assert any(e.startswith("wire_complete") for e in errors)

    _write_yaml(
        impl,
        _base_implement(
            step_id="s04",
            title="enforce x",
            status="completed",
            decompose_ref=str(dec.relative_to(root)),
            wire_complete={
                "call_sites": ["loop.runner"],
                "enforce_path": "bin/pytest loop/tests/test_x.py -q",
                "dual_path_rg": "rg old_path loop/",
                "instruction_rg": "rg old-format .cursor/rules/",
                "deny_old_proven": True,
            },
        ),
    )
    errors_ok = validate_implement_yaml(impl, finish=True, cwd=root)
    assert not any(e.startswith("wire_complete") for e in errors_ok)


def test_implement_load_state_not_completed_without_wire_block(tmp_path: Path):
    root = tmp_path
    dec = root / "memory-bank/back/plan/T-HUB-TEST/yaml/steps/s06-legacy-fallback-purge.yaml"
    impl = root / "memory-bank/back/implement/T-HUB-TEST/s06-legacy-fallback-purge.yaml"
    _write_yaml(
        dec,
        _base_decompose(
            step_id="s06",
            title="legacy-fallback-purge",
            wire_complete_required=True,
            checkpoints=[
                {"id": "cp1", "criterion": "deny", "verify": "rg legacy loop/"}
            ],
        ),
    )
    _write_yaml(
        impl,
        _base_implement(
            step_id="s06",
            title="legacy-fallback-purge",
            status="completed",
            decompose_ref=str(dec.relative_to(root)),
        ),
    )
    rel = impl.relative_to(root).as_posix()
    state = implement_load_state(root, rel)
    assert state["ok"] is True
    assert state["completed"] is False
