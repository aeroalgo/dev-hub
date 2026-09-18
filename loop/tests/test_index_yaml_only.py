from __future__ import annotations

import importlib.util
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


def _load_index():
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location("epic_index_test_yaml_only", HOOKS / "epic_index.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_mark_index_step_status_writes_yaml_not_md(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/decompose-demo"
    yaml_body = (
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  status: pending\n"
    )
    md_body = (
        "| step_id | title | status |\n"
        "| :--- | :--- | :--- |\n"
        "| **s01** | demo | pending |\n"
    )
    _write(tmp_path, f"{base}/index.yaml", yaml_body)
    _write(tmp_path, f"{base}/index.md", md_body)

    res = lib.mark_index_step_status(tmp_path, f"{base}/index.yaml", "s01", "completed")
    assert res.get("ok") is True

    # Read yaml back and verify status is completed
    updated_yaml = (tmp_path / base / "index.yaml").read_text(encoding="utf-8")
    assert "status: completed" in updated_yaml


def test_rebuild_md_from_yaml(tmp_path: Path) -> None:
    idx = _load_index()
    base = "memory-bank/back/plan/decompose-demo"
    yaml_body = (
        "schema: epic-decompose-index/v1\n"
        "plan_id: demo\n"
        "status_canon: index.yaml\n"
        "steps:\n"
        "- id: s01\n"
        "  file: s01.yaml\n"
        "  title: demo step\n"
        "  status: completed\n"
    )
    _write(tmp_path, f"{base}/index.yaml", yaml_body)
    _write(tmp_path, f"{base}/index.md", "# Old MD\n")

    res = idx.rebuild_md_queue_from_yaml(tmp_path / base / "index.md")
    assert res.get("ok") is True

    updated_md = (tmp_path / base / "index.md").read_text(encoding="utf-8")
    assert "s01" in updated_md
    assert "completed" in updated_md


def test_load_decompose_steps_fail_closed_rejects_missing_yaml(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/decompose-demo"
    _write(tmp_path, f"{base}/index.md", "| **s01** | demo | pending |\n")

    res = lib.load_decompose_steps_fail_closed(tmp_path, f"{base}/index.md")
    assert res["ok"] is False
    assert res["diagnostic_code"] == "index_not_found"
    assert res["steps"] == []


def test_runtime_index_resolution_reads_yaml_when_md_mirror_exists(tmp_path: Path) -> None:
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
    _write(tmp_path, f"{base}/md/decompose-index.md", "| s01 | pending |\n")

    result = lib.load_decompose_steps_fail_closed(
        tmp_path,
        f"{base}/md/decompose-index.md",
    )
    assert result["ok"] is True
    assert Path(result["index"]) == yaml_path


def test_runtime_index_resolver_never_returns_md(tmp_path: Path) -> None:
    from harness.hooks.epic_paths import find_decompose_index_path

    epic = "T-YAML-ONLY"
    md_only = tmp_path / f"memory-bank/back/plan/{epic}/md/decompose-index.md"
    md_only.parent.mkdir(parents=True, exist_ok=True)
    md_only.write_text("# mirror only\n", encoding="utf-8")
    assert find_decompose_index_path(tmp_path, "back", epic) is None

    yaml_path = tmp_path / f"memory-bank/back/plan/{epic}/yaml/decompose-index.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        "schema: epic-decompose-index/v1\nplan_id: T-YAML-ONLY\nsteps: []\n",
        encoding="utf-8",
    )
    resolved = find_decompose_index_path(tmp_path, "back", epic)
    assert resolved == yaml_path
    assert resolved.suffix == ".yaml"


def test_mark_index_step_status_fails_closed_without_yaml(tmp_path: Path) -> None:
    lib = _load_lib()
    base = "memory-bank/back/plan/decompose-demo"
    _write(tmp_path, f"{base}/index.md", "| **s01** | demo | pending |\n")

    res = lib.mark_index_step_status(tmp_path, f"{base}/index.md", "s01", "completed")
    assert res["ok"] is False
    assert "missing decompose index" in res["error"]


def test_index_writers_use_shared_atomic_owner() -> None:
    core_source = Path("harness/hooks/epic/core.py").read_text(encoding="utf-8")
    parallel_source = Path("loop/parallel/orchestrator.py").read_text(encoding="utf-8")
    assert "ypath.write_text(dump_index_yaml(doc)" not in core_source
    assert "index_path.write_text(dump_index_yaml(doc)" not in parallel_source
    assert "atomic_write_text(ypath, dump_index_yaml(doc))" in core_source
    assert "atomic_write_text(index_path, dump_index_yaml(doc))" in parallel_source
