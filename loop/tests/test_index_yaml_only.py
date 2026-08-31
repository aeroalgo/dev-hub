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
    spec = importlib.util.spec_from_file_location("epic_lib_test_index_yaml_only", HOOKS / "epic_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
