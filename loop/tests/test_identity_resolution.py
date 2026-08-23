from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_lib():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("epic_lib_identity_resolution", HOOKS / "epic_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _state(cwd: Path, **extra: object) -> None:
    payload = {
        "active": True,
        "status": "armed",
        "armed_epic": "T-035-loop-state-prod-hardening",
        "armed_decompose": "memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/index.yaml",
    }
    payload.update(extra)
    _write(cwd, ".claude/runtime/epic/state.json", json.dumps(payload))


def _index(cwd: Path, *, role: str = "back", epic: str = "T-035-loop-state-prod-hardening") -> None:
    base = f"memory-bank/{role}/plan/decompose-{epic}"
    _write(cwd, f"{base}/index.md", "| step_id | title | status |\n| :--- | :--- | :--- |\n| **s11** | identity | pending |\n")
    _write(
        cwd,
        f"{base}/index.yaml",
        f"schema: epic-decompose-index/v1\nplan_id: {epic}\nsource_md: index.md\nstatus_canon: index.yaml\nsteps:\n- id: s11\n  file: s11-identity-index-fail-closed.yaml\n  next_phase: {role.upper()} IMPLEMENT\n  title: identity\n  status: pending\n",
    )


def test_identity_without_candidates_is_typed_not_found(tmp_path: Path) -> None:
    lib = _load_lib()

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "not_found"
    assert result["diagnostic_code"] == "identity_not_found"
    assert result["ok"] is False


def test_identity_with_two_role_candidates_is_ambiguous(tmp_path: Path) -> None:
    lib = _load_lib()
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- memory-bank/back/plan/decompose-one/index.md\n"
        "- memory-bank/front/plan/decompose-two/index.md\n",
    )

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "ambiguous"
    assert result["diagnostic_code"] == "identity_ambiguous"
    assert result["ok"] is False


def test_explicit_selector_resolves_stable_identity(tmp_path: Path) -> None:
    lib = _load_lib()
    _index(tmp_path)
    _state(tmp_path)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        "- memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/s11-identity-index-fail-closed.yaml\n"
        "- memory-bank/back/plan/decompose-T-035-loop-state-prod-hardening/index.yaml\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Следующий:** `BACK IMPLEMENT @s11`\n",
    )

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "resolved"
    assert result["ok"] is True
    assert result["role"] == "BACK"
    assert result["role_dir"] == "back"
    assert result["epic_id"] == "T-035-loop-state-prod-hardening"


def test_identity_mismatch_is_fail_closed(tmp_path: Path) -> None:
    lib = _load_lib()
    _index(tmp_path)
    _state(tmp_path, armed_epic="other-epic")

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "ambiguous"
    assert result["diagnostic_code"] == "identity_conflict"
    assert result["ok"] is False


def test_role_from_decompose_integ_path() -> None:
    lib = _load_lib()

    assert lib.role_from_decompose_path("memory-bank/integration/plan/decompose-x/") == "INTEG"
    assert lib.role_from_decompose_path("/integration/plan/foo/") == "INTEG"
    assert lib.role_from_decompose_path("memory-bank/back/plan/decompose-x/") == "BACK"


def test_unknown_role_is_invalid_not_integ_fallback(tmp_path: Path) -> None:
    lib = _load_lib()
    _write(
        tmp_path,
        "memory-bank/unknown/plan/decompose-demo/index.md",
        "| step_id | title | status |\n| :--- | :--- | :--- |\n| **s01** | demo | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n- memory-bank/unknown/plan/decompose-demo/index.md\n",
    )

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "invalid"
    assert result["diagnostic_code"] == "identity_invalid"
    assert result["ok"] is False
