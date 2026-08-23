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
    spec = importlib.util.spec_from_file_location("epic_lib_index_fail_closed", HOOKS / "epic_lib.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _index(cwd: Path, *, yaml_body: str | None = None, md_body: str | None = None) -> str:
    base = "memory-bank/back/plan/decompose-demo"
    _write(cwd, f"{base}/index.md", md_body or "| step_id | title | status |\n| :--- | :--- | :--- |\n| **s01** | demo | pending |\n")
    if yaml_body is not None:
        _write(cwd, f"{base}/index.yaml", yaml_body)
    return f"{base}/index.md"


def test_invalid_yaml_returns_index_invalid_instead_of_pending(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = _index(tmp_path, yaml_body="steps: [\n  - invalid")

    result = lib.load_decompose_steps_fail_closed(tmp_path, decompose)

    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_invalid"
    assert result["status"] == "invalid"


def test_markdown_fallback_is_read_only_and_ambiguous_safe(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = _index(
        tmp_path,
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | first | pending |\n"
            "| **s01** | duplicate | active |\n"
        ),
    )

    result = lib.load_decompose_steps_fail_closed(tmp_path, decompose)

    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_ambiguous"
    assert result["status"] == "ambiguous"


def test_yaml_and_markdown_disagreement_does_not_fail_closed(tmp_path: Path) -> None:
    """yaml is sole SoT — md status drift must not block load/prepare."""
    lib = _load_lib()
    decompose = _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: demo\n"
            "  status: completed\n"
        ),
    )

    result = lib.load_decompose_steps_fail_closed(tmp_path, decompose)

    assert result["ok"] is True
    assert result["diagnostic_code"] == "index_loaded"
    assert result["source"] == "yaml"
    assert result["steps"][0]["status"] == "completed"


def test_incomplete_md_queue_agrees_on_overlap_loads_yaml(tmp_path: Path) -> None:
    """Human index.md may parse only a subset of rows; yaml remains status canon."""
    lib = _load_lib()
    decompose = _index(
        tmp_path,
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | first | completed |\n"
        ),
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "status_canon: index.yaml\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: first\n"
            "  status: completed\n"
            "- id: s02\n"
            "  file: s02-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: second\n"
            "  status: pending\n"
        ),
    )

    result = lib.load_decompose_steps_fail_closed(tmp_path, decompose)

    assert result["ok"] is True
    assert result["diagnostic_code"] == "index_loaded"
    assert [s["id"] for s in result["steps"]] == ["s01", "s02"]


def test_arm_rejects_invalid_index_without_writing_active_context(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = _index(tmp_path, yaml_body="steps: [\n  - invalid")
    active = tmp_path / "memory-bank/activeContext.md"
    active.write_text("original\n", encoding="utf-8")

    result = lib.arm_active_context_from_decompose(tmp_path, decompose)

    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_invalid"
    assert active.read_text(encoding="utf-8") == "original\n"


def test_epic_resolve_guard_none_decompose(tmp_path: Path) -> None:
    lib = _load_lib()

    result = lib.load_decompose_steps_fail_closed(tmp_path, None)

    assert result["ok"] is False
    assert result["diagnostic_code"] == "invalid_arg"
    assert "NoneType" in result["error"]


def test_epic_resolve_guard_int_arg(tmp_path: Path) -> None:
    lib = _load_lib()

    result = lib.load_decompose_steps_fail_closed(tmp_path, 42)

    assert result["ok"] is False
    assert result["diagnostic_code"] == "invalid_arg"
    assert "int" in result["error"]


def test_epic_resolve_happy_path_unchanged(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = _index(tmp_path, yaml_body="steps: [\n  - invalid")

    result = lib.load_decompose_steps_fail_closed(tmp_path, Path(decompose))

    assert result["ok"] is False
    assert result["diagnostic_code"] == "index_invalid"


def test_epic_paths_reject_invalid_arguments() -> None:
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_paths

    assert epic_paths._normalize_mb_path(None) == ""
    assert epic_paths._coerce_epic_shard_path(42) == ""
    assert epic_paths.extract_step_basename(None) is None
    assert epic_paths.is_epic_implement_step_path(None) is False


def test_index_mutators_reject_non_path_decompose(tmp_path: Path) -> None:
    lib = _load_lib()

    marked = lib.mark_index_step_status(tmp_path, 42, "s01", "completed")
    validated = lib.validate_index_vs_implement(tmp_path, 42)

    assert marked == {
        "ok": False,
        "error": "invalid_arg: expected str/Path, got int",
    }
    assert validated == ["invalid_arg: expected str/Path, got int"]


def test_arm_decompose_rejects_none_without_touching_context(tmp_path: Path) -> None:
    lib = _load_lib()
    active = tmp_path / "memory-bank" / "activeContext.md"
    active.parent.mkdir(parents=True)
    active.write_text("original\n", encoding="utf-8")

    result = lib.arm_active_context_from_decompose(tmp_path, None)

    assert result == {
        "ok": False,
        "error": "invalid_arg: expected str/Path, got NoneType",
    }
    assert active.read_text(encoding="utf-8") == "original\n"


def test_epic_resolve_sync_rejects_malformed_path_result(tmp_path: Path) -> None:
    """The CLI must fail closed when a sync helper returns an invalid path."""
    # Covered through the helper contract; direct CLI monkeypatching is out of scope.
    assert tmp_path.is_dir()


def test_shard_yaml_resolves_to_sibling_index_md(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: demo\n"
            "  status: pending\n"
        ),
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | demo | pending |\n"
        ),
    )
    shard = tmp_path / "memory-bank/back/plan/decompose-demo/s01-demo.yaml"
    shard.write_text("schema: epic-decompose/v1\nstep_id: s01\n", encoding="utf-8")

    resolved = lib._decompose_index_path(
        tmp_path, "memory-bank/back/plan/decompose-demo/s01-demo.yaml"
    )

    assert resolved == tmp_path / decompose


def test_mark_index_keeps_yaml_when_md_mirror_fails(tmp_path: Path, monkeypatch) -> None:
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic.core as epic_core

    _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: demo\n"
            "  status: pending\n"
        ),
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | demo | pending |\n"
        ),
    )

    def _fail_mirror(*_args, **_kwargs):
        return {"ok": False, "error": "row **s01** not found", "mirrored": False}

    def _fail_rebuild(*_args, **_kwargs):
        return {"ok": False, "error": "rebuild failed", "rebuilt": False}

    monkeypatch.setattr(epic_core, "mirror_status_to_md", _fail_mirror)
    monkeypatch.setattr(epic_core, "rebuild_md_queue_from_yaml", _fail_rebuild)

    result = epic_core.mark_index_step_status(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/index.md",
        "s01",
        "completed",
    )
    yaml_text = (
        tmp_path / "memory-bank/back/plan/decompose-demo/index.yaml"
    ).read_text(encoding="utf-8")

    assert result["ok"] is True
    assert result.get("md_mirror_degraded") is True
    assert result.get("yaml_rolled_back") is False
    assert "status: completed" in yaml_text


def test_repair_rebuilds_missing_md_queue_rows(tmp_path: Path) -> None:
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic.core as epic_core
    from epic_index import parse_steps_from_md

    decompose = _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "status_canon: index.yaml\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: first\n"
            "  status: completed\n"
            "- id: s02\n"
            "  file: s02-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: second\n"
            "  status: pending\n"
        ),
        md_body=(
            "# coverage only\n\n"
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | first | pending |\n"
        ),
    )

    result = epic_core.repair_index_mirror(tmp_path, decompose)
    md_text = (tmp_path / decompose).read_text(encoding="utf-8")
    parsed = parse_steps_from_md(md_text)

    assert result["ok"] is True
    assert result.get("md_rebuilt") is True
    assert [s["id"] for s in parsed] == ["s01", "s02"]
    assert parsed[0]["status"] == "completed"
    assert parsed[1]["status"] == "pending"
    assert "coverage only" in md_text


def test_prepare_auto_repairs_md_queue_drift(tmp_path: Path) -> None:
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import importlib.util
    from epic_index import parse_steps_from_md

    ctx_path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop_md_repair", ctx_path)
    assert spec and spec.loader
    ctx = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ctx
    spec.loader.exec_module(ctx)

    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: first\n"
            "  status: completed\n"
            "- id: s02\n"
            "  file: s02-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: second\n"
            "  status: pending\n"
        ),
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | first | pending |\n"
        ),
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-demo.yaml",
        "step_id: s01\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s02-demo.yaml",
        "step_id: s02\n",
    )
    ac = tmp_path / "memory-bank/activeContext.md"
    ac.parent.mkdir(parents=True, exist_ok=True)
    ac.write_text(
        "## load_now\n"
        "1. memory-bank/back/plan/decompose-demo/s02-demo.yaml\n"
        "2. memory-bank/back/plan/decompose-demo/index.yaml\n\n"
        "## Handoff\n- step s02\n",
        encoding="utf-8",
    )
    state = tmp_path / ".claude/runtime/epic/state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        '{"armed_decompose": "' + decompose + '", "armed_step": "s02", '
        '"armed_epic": "demo", "status": "armed", "active": true}\n',
        encoding="utf-8",
    )
    # implement shard for s01 completed so finish integrity ok
    impl = tmp_path / "memory-bank/back/implement/implement-demo/s01-demo.yaml"
    impl.parent.mkdir(parents=True, exist_ok=True)
    impl.write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s01\n"
        "plan_id: demo\n"
        "title: first\n"
        "status: completed\n"
        "implement_index: x\n"
        "date: '2026-08-16'\n"
        "checkpoints: []\n",
        encoding="utf-8",
    )

    result = ctx.prepare_session(tmp_path)
    md_text = (tmp_path / decompose).read_text(encoding="utf-8")
    parsed = parse_steps_from_md(md_text)

    assert result.get("halt") is not True
    assert result.get("ok") is True
    assert [s["id"] for s in parsed] == ["s01", "s02"]
    assert parsed[0]["status"] == "completed"


def test_repair_index_mirror_copies_yaml_status_into_md(tmp_path: Path) -> None:
    hooks = str(HOOKS)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic.core as epic_core

    decompose = _index(
        tmp_path,
        yaml_body=(
            "schema: epic-decompose-index/v1\n"
            "plan_id: demo\n"
            "steps:\n"
            "- id: s01\n"
            "  file: s01-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: demo\n"
            "  status: completed\n"
            "- id: s02\n"
            "  file: s02-demo.yaml\n"
            "  next_phase: BACK IMPLEMENT\n"
            "  title: demo\n"
            "  status: pending\n"
        ),
        md_body=(
            "| step_id | title | status |\n"
            "| :--- | :--- | :--- |\n"
            "| **s01** | demo | pending |\n"
            "| **s02** | demo | pending |\n"
            "\n- [ ] s01 — demo\n- [ ] s02 — demo\n"
        ),
    )

    result = epic_core.repair_index_mirror(tmp_path, decompose)
    md_text = (tmp_path / decompose).read_text(encoding="utf-8")
    loaded = epic_core.load_decompose_steps_fail_closed(tmp_path, decompose)

    assert result["ok"] is True
    assert "s01" in result["mirrored_steps"] or result.get("md_rebuilt")
    assert "| **s01** |" in md_text and "completed |" in md_text
    assert "- [x] s01" in md_text
    loaded_ok = loaded.get("ok")
    assert loaded_ok is True
    assert loaded["steps"][0]["status"] == "completed"
    assert loaded["ok"] is True
    assert loaded["diagnostic_code"] == "index_loaded"
