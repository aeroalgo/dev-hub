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


def test_identity_resolves_by_plan_id_when_folder_slug_differs(tmp_path: Path) -> None:
    lib = _load_lib()
    epic = "T-050-partner-rules-alembic-port"
    base = f"memory-bank/back/plan/decompose-T-050"
    _write(tmp_path, f"{base}/index.md", "| step_id | title | status |\n| **s01** | demo | pending |\n")
    _write(
        tmp_path,
        f"{base}/index.yaml",
        f"schema: epic-decompose-index/v1\nplan_id: {epic}\nsource_md: index.md\nstatus_canon: index.yaml\nsteps:\n- id: s01\n  file: s01-demo.yaml\n  next_phase: BACK IMPLEMENT\n  title: demo\n  status: pending\n",
    )
    _write(tmp_path, f"{base}/s01-demo.yaml", "schema: epic-decompose/v1\nrole: back\nstep_id: s01\ntitle: demo\ngoal: demo\nas_built: []\ndelta: []\ndeletes: []\ncheckpoints: []\n")
    _state(tmp_path, armed_epic=epic, armed_decompose=None)
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n"
        f"- `memory-bank/back/plan/decompose-T-050/s01-demo.yaml`\n\n"
        "## Handoff BACK IMPLEMENT\n"
        "- **Режим/шаг:** `BACK IMPLEMENT s01`\n",
    )

    result = lib.resolve_pipeline_identity(tmp_path)

    assert result["status"] == "resolved"
    assert result["ok"] is True
    assert result["epic_id"] == epic


def test_find_decompose_index_by_plan_id(tmp_path: Path) -> None:
    import sys

    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    sys.path.insert(0, str(ROOT / "loop"))
    from epic_paths import find_decompose_index_path

    epic = "T-050-partner-rules-alembic-port"
    base = tmp_path / "memory-bank/back/plan/decompose-T-050"
    base.mkdir(parents=True)
    (base / "index.yaml").write_text(
        f"schema: epic-decompose-index/v1\nplan_id: {epic}\nsteps: []\n",
        encoding="utf-8",
    )

    found = find_decompose_index_path(tmp_path, "back", epic)

    assert found is not None
    assert found.name == "index.yaml"


def test_find_decompose_index_plan_slug_resolves_queue_prefix_folder(tmp_path: Path) -> None:
    import sys

    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from epic_paths import find_decompose_index_path

    plan_dir = tmp_path / "memory-bank/back/plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-030-harness-runtime-wire.md").write_text("# plan\n", encoding="utf-8")
    decomp = plan_dir / "decompose-T-HUB-030"
    decomp.mkdir()
    (decomp / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-HUB-030\nsteps: []\n",
        encoding="utf-8",
    )

    found = find_decompose_index_path(
        tmp_path, "back", "T-HUB-030-harness-runtime-wire"
    )

    assert found is not None
    assert found.parent.name == "decompose-T-HUB-030"


def test_resolve_epic_next_action_plan_slug_finds_short_decompose(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "loop"))
    from loop.board_sync.epic_resolver import resolve_epic_next_action

    plan_dir = tmp_path / "memory-bank/back/plan"
    analyze_dir = tmp_path / "memory-bank/back/analyze/T-HUB-030"
    plan_dir.mkdir(parents=True)
    analyze_dir.mkdir(parents=True)
    (plan_dir / "plan-T-HUB-030-harness-runtime-wire.md").write_text("# plan\n", encoding="utf-8")
    decomp = plan_dir / "decompose-T-HUB-030"
    decomp.mkdir()
    (decomp / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-HUB-030\nsteps:\n"
        "  - id: s01\n    status: pending\n",
        encoding="utf-8",
    )
    (analyze_dir / "analyze-20260831-harness-runtime-wire.yaml").write_text(
        "schema: epic-analyze/v1\nmetrics:\n  critical_count: 0\n",
        encoding="utf-8",
    )

    res = resolve_epic_next_action(tmp_path, "back", "T-HUB-030-harness-runtime-wire")

    assert res.reason_code != "decompose_missing"
    assert res.decompose_rel == "memory-bank/back/plan/decompose-T-HUB-030/index.yaml"
    assert res.phase == "IMPLEMENT"


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
