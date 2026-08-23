from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml

from loop.dag import adapt_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[2]
CANARY_MANIFEST = ROOT / "loop" / "dag" / "canary-finish-integrity.yaml"


def _load_ctx():
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_canary", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec.loader.exec_module(mod)
    return mod


def _write_artifact(cwd: Path, name: str) -> None:
    path = cwd / "loop" / "tests" / "fixtures" / "canary" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("status: completed\nintegration_gate: pass\n", encoding="utf-8")


def test_canary_manifest_validate_and_order(tmp_path: Path) -> None:
    manifest = yaml.safe_load(CANARY_MANIFEST.read_text(encoding="utf-8"))

    adapted = adapt_manifest(manifest)
    validation = validate_manifest(manifest)

    assert adapted["ok"] is True
    assert validation["ok"] is True
    assert [node["id"] for node in manifest["nodes"]] == [
        "validate_finish",
        "check_after",
        "prepare_session",
    ]
    assert all(node["completion"] == {"type": "artifact"} for node in manifest["nodes"])

    dag_path = tmp_path / "loop" / "dag" / "canary-finish-integrity.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(CANARY_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    ctx = _load_ctx()

    out = ctx._arm_dag_next(tmp_path, "canary-finish-integrity")
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert out["blocked"] == {"validate_finish": ["completion_contract"]}

    _write_artifact(tmp_path, "validate-finish.yaml")
    out = ctx._arm_dag_next(tmp_path, "canary-finish-integrity")
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert out["dag_done"] == ["validate_finish"]
    assert out["blocked"] == {"check_after": ["completion_contract"]}

    _write_artifact(tmp_path, "check-after.yaml")
    out = ctx._arm_dag_next(tmp_path, "canary-finish-integrity")
    assert out["diagnostic"]["code"] == "dag_blocked"
    assert out["dag_done"] == ["check_after", "validate_finish"]
    assert out["blocked"] == {"prepare_session": ["completion_contract"]}

    _write_artifact(tmp_path, "prepare-session.yaml")
    out = ctx._arm_dag_next(tmp_path, "canary-finish-integrity")
    assert out["complete"] is True
    assert out["dag_done"] == ["check_after", "prepare_session", "validate_finish"]


def test_default_load_dag_skips_canary_and_demo_fixtures(tmp_path: Path) -> None:
    ctx = _load_ctx()
    dag_dir = tmp_path / "loop" / "dag"
    dag_dir.mkdir(parents=True)
    (dag_dir / "canary-finish-integrity.yaml").write_text(
        CANARY_MANIFEST.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (dag_dir / "integ-demo.yaml").write_text(
        "schema: loop-dag/v2\n"
        "pipeline:\n"
        "  id: integ-demo\n"
        "nodes: []\n",
        encoding="utf-8",
    )

    assert ctx._load_dag(tmp_path) is None
    assert ctx._load_dag(tmp_path, "canary-finish-integrity")["pipeline"]["id"] == (
        "canary-finish-integrity"
    )

    out = ctx._arm_dag_next(tmp_path)
    assert out["ok"] is True
    assert out["armed"] is False
    assert out.get("reason") == "DAG manifest not found"