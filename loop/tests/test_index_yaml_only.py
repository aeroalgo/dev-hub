from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def _load_lib():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic
    return epic


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_mark_index_step_status_writes_validated_yaml(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/demo/yaml"
    yaml_body = (
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  status: pending\n"
    )
    _write(tmp_path, f"{base}/decompose-index.yaml", yaml_body)

    res = lib.mark_index_step_status(tmp_path, f"{base}/decompose-index.yaml", "s01", "completed")
    assert res.get("ok") is True

    # Read yaml back and verify status is completed
    updated_yaml = (tmp_path / base / "decompose-index.yaml").read_text(encoding="utf-8")
    assert "status: completed" in updated_yaml


def test_runtime_index_resolution_reads_validated_yaml(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/demo"
    yaml_path = tmp_path / base / "yaml" / "decompose-index.yaml"
    _write(
        tmp_path,
        f"{base}/yaml/decompose-index.yaml",
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  status: pending\n",
    )
    result = lib.load_decompose_steps_fail_closed(
        tmp_path,
        f"{base}/yaml/decompose-index.yaml",
    )
    assert result["ok"] is True
    assert Path(result["index"]) == yaml_path


def test_mark_index_step_status_fails_closed_without_yaml(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/demo/yaml"

    res = lib.mark_index_step_status(tmp_path, f"{base}/decompose-index.yaml", "s01", "completed")
    assert res["ok"] is False
    assert "missing decompose index" in res["error"]


def test_index_writers_use_shared_atomic_owner() -> None:
    core_source = Path("harness/hooks/epic/core.py").read_text(encoding="utf-8")
    parallel_source = Path("loop/parallel/orchestrator.py").read_text(encoding="utf-8")
    assert "ypath.write_text(dump_index_yaml(doc)" not in core_source
    assert "index_path.write_text(dump_index_yaml(doc)" not in parallel_source
    assert "atomic_write_text(ypath, dump_index_yaml(doc))" in core_source
    assert "atomic_write_text(index_path, dump_index_yaml(doc))" in parallel_source
