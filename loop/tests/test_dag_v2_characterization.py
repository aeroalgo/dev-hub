from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))
if str(ROOT / "loop") not in sys.path:
    sys.path.insert(0, str(ROOT / "loop"))

from dag import (  # noqa: E402
    adapt_manifest,
    dag_advance_epic,
    migrate_manifest,
    validate_manifest,
)
import roadmap_queue  # noqa: E402


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_dag_v2_char", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _canonical_v2_manifest() -> dict:
    return {
        "schema": "loop-dag/v2",
        "pipeline": {"id": "portal"},
        "source": {
            "kind": "manifest",
            "artifacts": ["loop/dag/portal.yaml"],
        },
        "execution": {"autonomous": True},
        "nodes": [
            {
                "id": "back-core",
                "role": "BACK",
                "decompose": "memory-bank/back/plan/decompose-core/index.md",
                "depends_on": [],
                "completion": {"type": "decompose"},
                "action": "implement",
            },
            {
                "id": "front-ui",
                "role": "FRONT",
                "decompose": "memory-bank/front/plan/decompose-ui/index.md",
                "depends_on": ["back-core"],
                "completion": {"type": "decompose"},
                "action": "implement",
            },
            {
                "id": "integ-close",
                "role": "INTEG",
                "artifact": "memory-bank/integration/gap/portal/gap-portal.yaml",
                "depends_on": ["front-ui"],
                "completion": {"type": "artifact"},
                "action": "close",
            },
        ],
    }


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_v2_dag_manifest_canonical_validation() -> None:
    """Characterize valid canonical v2 manifest acceptance."""
    manifest = _canonical_v2_manifest()
    result = validate_manifest(manifest)

    assert result["ok"] is True
    assert result["diagnostics"] == []
    assert result["manifest"]["schema"] == "loop-dag/v2"
    assert result["manifest"]["pipeline"]["id"] == "portal"
    assert result["manifest"]["execution"]["autonomous"] is True


def test_v2_dag_manifest_strict_denial_diagnostics() -> None:
    """Characterize strict validation rejections on non-v2 schemas and malformed fields."""
    base = _canonical_v2_manifest()

    # Schema must be loop-dag/v2
    bad_schema = dict(base, schema="loop-dag/v1")
    res_schema = validate_manifest(bad_schema)
    assert res_schema["ok"] is False
    assert any(d["code"] == "schema_invalid" for d in res_schema["diagnostics"])

    # Missing or empty pipeline.id
    bad_pipeline = dict(base, pipeline={"id": ""})
    res_pipeline = validate_manifest(bad_pipeline)
    assert res_pipeline["ok"] is False
    assert any(d["code"] == "ambiguous_pipeline" for d in res_pipeline["diagnostics"])

    # Missing or non-bool execution.autonomous
    bad_exec = dict(base, execution={"autonomous": "yes"})
    res_exec = validate_manifest(bad_exec)
    assert res_exec["ok"] is False
    assert any(d["code"] == "schema_invalid" for d in res_exec["diagnostics"])

    # Unknown role
    bad_role = _canonical_v2_manifest()
    bad_role["nodes"][0]["role"] = "TESTER"
    res_role = validate_manifest(bad_role)
    assert res_role["ok"] is False
    assert any(d["code"] == "role_unknown" for d in res_role["diagnostics"])

    # Missing dependency
    bad_dep = _canonical_v2_manifest()
    bad_dep["nodes"][1]["depends_on"] = ["nonexistent-node"]
    res_dep = validate_manifest(bad_dep)
    assert res_dep["ok"] is False
    assert any(d["code"] == "missing_dependency" for d in res_dep["diagnostics"])

    # Cyclic dependency
    bad_cycle = _canonical_v2_manifest()
    bad_cycle["nodes"][0]["depends_on"] = ["front-ui"]
    res_cycle = validate_manifest(bad_cycle)
    assert res_cycle["ok"] is False
    assert any(d["code"] == "cycle" for d in res_cycle["diagnostics"])

    # Reserved role slug in decompose epic_id
    bad_slug = _canonical_v2_manifest()
    bad_slug["nodes"][0]["decompose"] = "memory-bank/back/plan/decompose-back/index.md"
    res_slug = validate_manifest(bad_slug)
    assert res_slug["ok"] is False
    assert any(d["code"] == "epic_id_reserved" for d in res_slug["diagnostics"])


def test_legacy_v1_manifest_adapter_and_migration_boundary() -> None:
    """Characterize legacy v1 adapter and compatibility mode requirements."""
    v1_manifest = {
        "schema": "loop-dag/v1",
        "pipeline_id": "portal",
        "nodes": [
            {
                "id": "back-core",
                "role_dir": "back",
                "decompose": "memory-bank/back/plan/decompose-core/index.md",
                "depends_on": [],
            },
            {
                "id": "front-ui",
                "role_dir": "front",
                "decompose": "memory-bank/front/plan/decompose-ui/index.md",
                "depends_on": ["back-core"],
            },
        ],
    }

    # Direct validation strictly rejects v1
    val = validate_manifest(v1_manifest)
    assert val["ok"] is False
    assert any(d["code"] == "schema_invalid" for d in val["diagnostics"])

    # adapt_manifest converts v1 but sets autonomous=False and marks legacy_gap_inference
    adapted = adapt_manifest(v1_manifest)
    assert adapted["ok"] is True
    assert adapted["autonomous"] is False
    assert adapted["manifest"]["schema"] == "loop-dag/v2"
    assert len(adapted["manifest"]["nodes"]) == 2
    assert any(d["code"] == "legacy_gap_inference" for d in adapted["diagnostics"])

    # migrate_manifest requires compatibility_mode=True
    mig_no_compat = migrate_manifest(v1_manifest, compatibility_mode=False)
    assert mig_no_compat["ok"] is False
    assert any(d["code"] == "compatibility_mode_required" for d in mig_no_compat["diagnostics"])

    mig_compat = migrate_manifest(v1_manifest, compatibility_mode=True)
    assert mig_compat["ok"] is True
    assert mig_compat["migrated"] is True
    assert mig_compat["manifest"]["schema"] == "loop-dag/v2"
    assert len(mig_compat["manifest"]["nodes"]) == 2


def test_context_loop_arm_dag_next_execution(tmp_path: Path) -> None:
    """Characterize _arm_dag_next arming ready node and updating state."""
    ctx = _load_ctx()
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n1. old\n")

    manifest = {
        "schema": "loop-dag/v2",
        "pipeline": {"id": "portal"},
        "source": {"kind": "manifest", "artifacts": ["loop/dag/portal.yaml"]},
        "execution": {"autonomous": True},
        "nodes": [
            {
                "id": "node-1",
                "role": "BACK",
                "decompose": "memory-bank/back/plan/decompose-core/index.md",
                "depends_on": [],
                "completion": {"type": "decompose"},
                "action": "implement",
            },
        ],
    }
    _write(tmp_path, "loop/dag/portal.yaml", yaml.safe_dump(manifest, sort_keys=False))
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-core/index.md",
        "| step_id | title | status |\n|---|---|---|\n| **s01** | [s01-step.yaml](s01-step.yaml) | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-core/s01-step.yaml",
        "schema: epic-decompose/v1\nstep_id: s01\n",
    )

    out = ctx._arm_dag_next(tmp_path, "portal")

    assert out["ok"] is True
    assert out["armed"] is True
    assert out["node"] == "node-1"
    assert out["ready"] == ["node-1"]
    assert out["execution"] == "sequential"

    state = ctx.load_epic_state(tmp_path)
    assert state.get("dag_pipeline") == "portal"
    assert state.get("dag_cursor") == "node-1"


def test_context_loop_arm_dag_next_diagnostics_when_missing_or_invalid(tmp_path: Path) -> None:
    """Characterize _arm_dag_next failure diagnostics when manifest missing or invalid."""
    ctx = _load_ctx()

    # Missing manifest
    missing_out = ctx._arm_dag_next(tmp_path, "nonexistent-pipeline")
    assert missing_out["ok"] is False
    assert missing_out["diagnostic"]["code"] == "dag_manifest_missing"

    # Malformed manifest
    _write(tmp_path, "loop/dag/broken.yaml", "schema: loop-dag/invalid\n")
    broken_out = ctx._arm_dag_next(tmp_path, "broken")
    assert broken_out["ok"] is False
    assert broken_out["diagnostic"]["code"] == "dag_schema_invalid"


def test_dag_advance_epic_wrapper_delegation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Characterize dag_advance_epic routing to epic_transition."""
    called = {}

    def mock_resolve_next(cwd: Path | str, epic_id: str, role: str):
        from loop.board_sync.epic_resolver import EpicNextAction
        return EpicNextAction(epic_id=epic_id, role=role, next_command="implement", phase="IMPLEMENT")

    def mock_arm_phase(cwd: Path | str, epic_id: str, phase: str, role: str, **kwargs) -> dict:
        called["cwd"] = cwd
        called["epic_id"] = epic_id
        called["phase"] = phase
        called["role"] = role
        return {"ok": True, "armed_epic": epic_id, "phase": phase}

    import loop.epic_transition as et
    monkeypatch.setattr(et, "resolve_next", mock_resolve_next)
    monkeypatch.setattr(et, "arm_phase", mock_arm_phase)

    res = dag_advance_epic(tmp_path, "T-HUB-089", "back")
    assert res["ok"] is True
    assert called["epic_id"] == "T-HUB-089"
    assert called["role"] == "back"
    assert called["phase"] == "IMPLEMENT"


def test_v2_roadmap_queue_characterization(tmp_path: Path) -> None:
    """Characterize v2 roadmap queue contracts and legacy fallback resolution."""
    assert roadmap_queue.QUEUE_VERSION == "roadmap-queue/v2"
    assert roadmap_queue.DEFAULT_QUEUE == "memory-bank/back/roadmap/queue.yaml"

    # Canonical v2 queue loading
    v2_queue_content = {
        "version": "roadmap-queue/v2",
        "role": "back",
        "queue": [
            {"id": "epic-1", "plan": "plan-epic-1.md", "deps": []},
            {"id": "epic-2", "plan": "plan-epic-2.md", "deps": ["epic-1"]},
        ],
        "done": [],
    }
    _write(tmp_path, "memory-bank/back/roadmap/queue.yaml", yaml.safe_dump(v2_queue_content, sort_keys=False))

    loaded = roadmap_queue.parse_roadmap_queue(tmp_path)
    assert loaded["ok"] is True
    assert loaded["version"] == "roadmap-queue/v2"
    assert len(loaded["queue"]) == 2
    assert loaded["queue"][0]["id"] == "epic-1"

    # Rejection of unsupported queue version
    bad_version_content = dict(v2_queue_content, version="roadmap-queue/v99")
    _write(tmp_path, "memory-bank/back/roadmap/queue.yaml", yaml.safe_dump(bad_version_content, sort_keys=False))
    bad_loaded = roadmap_queue.parse_roadmap_queue(tmp_path)
    assert bad_loaded["ok"] is False
    assert bad_loaded["error"] == "queue_version_mismatch"

    # Legacy path mapping function
    assert roadmap_queue.queue_rel_from_roadmap("memory-bank/back/roadmap") == "memory-bank/back/roadmap/queue.yaml"
    with pytest.raises(ValueError, match="legacy .md roadmap path is forbidden"):
        roadmap_queue.queue_rel_from_roadmap("memory-bank/back/plan/roadmap-epics.md")
