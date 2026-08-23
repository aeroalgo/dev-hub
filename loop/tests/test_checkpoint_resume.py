from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
RESILIENCE = HOOKS / "session_resilience.py"
EPIC_RESOLVE = HOOKS / "epic_resolve.py"


def _load_module(path: Path, name: str):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_resilience():
    return _load_module(RESILIENCE, "checkpoint_resume_session_resilience")


def _load_epic_resolve():
    return _load_module(EPIC_RESOLVE, "checkpoint_resume_epic_resolve")


def make_mock_shard(
    tmp_path: Path,
    step_id: str = "s06",
    plan_id: str = "T-036-session-checkpoint-resume",
    checkpoints_list: list[dict[str, str]] | None = None,
) -> Path:
    checkpoints = checkpoints_list or [
        {"id": "cp1", "criterion": "first checkpoint", "status": "pending"},
        {"id": "cp2", "criterion": "second checkpoint", "status": "pending"},
    ]
    path = (
        tmp_path
        / "memory-bank/back/implement"
        / f"implement-{plan_id}"
        / f"{step_id}-checkpoint-resume.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-implement/v1",
                "role": "back",
                "step_id": step_id,
                "plan_id": plan_id,
                "task_id": "T-036",
                "title": "checkpoint resume tests",
                "status": "in_progress",
                "implement_index": (
                    "memory-bank/back/implement/"
                    f"implement-{plan_id}/index.md"
                ),
                "date": "2026-08-07",
                "checkpoints": checkpoints,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_plan_id_saved_in_last_session(tmp_path: Path) -> None:
    sr = _load_resilience()

    path = sr.write_last_session(
        tmp_path,
        track="epic",
        status="aborted",
        plan_id="T-999-test",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["plan_id"] == "T-999-test"


def test_plan_id_loaded_and_used(tmp_path: Path) -> None:
    sr = _load_resilience()
    sr.write_last_session(
        tmp_path,
        track="epic",
        status="aborted",
        plan_id="T-999-test",
    )

    assert sr.load_last_session(tmp_path)["plan_id"] == "T-999-test"


def test_backward_compat_no_plan_id(tmp_path: Path) -> None:
    sr = _load_resilience()
    path = sr.last_session_path(tmp_path, track="epic")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "aborted"}), encoding="utf-8")

    payload = sr.load_last_session(tmp_path)
    assert payload is not None
    assert payload.get("plan_id") is None


def test_write_last_session_plan_id_none(tmp_path: Path) -> None:
    sr = _load_resilience()

    path = sr.write_last_session(
        tmp_path,
        track="epic",
        status="clean",
        plan_id=None,
    )

    assert json.loads(path.read_text(encoding="utf-8"))["plan_id"] is None


def test_checkpoint_trace_injected_on_resume(tmp_path: Path) -> None:
    sr = _load_resilience()
    make_mock_shard(
        tmp_path,
        checkpoints_list=[
            {
                "id": "cp1",
                "criterion": "first checkpoint",
                "status": "done",
                "done_at": "2026-08-07T00:00:00Z",
            },
            {"id": "cp2", "criterion": "second checkpoint", "status": "pending"},
            {"id": "cp3", "criterion": "third checkpoint", "status": "pending"},
        ],
    )
    sr.git_dirty_paths = lambda _cwd: []

    lines = sr.dirty_resume_prompt_lines(
        tmp_path,
        step_id="s06",
        plan_id="T-036-session-checkpoint-resume",
        resume_from="s06",
        last={"status": "aborted", "reason": "API Error: terminated"},
    )

    text = "\n".join(lines)
    assert "## checkpoint_trace" in text
    assert "status: done" in text
    assert "resume_from_checkpoint: cp2" in text


def test_checkpoint_trace_skipped_no_shard(tmp_path: Path) -> None:
    sr = _load_resilience()

    assert sr.load_implement_checkpoint_trace(
        tmp_path, "s06", "T-036-session-checkpoint-resume"
    ) == []


def test_checkpoint_trace_all_done_skipped(tmp_path: Path) -> None:
    sr = _load_resilience()
    make_mock_shard(
        tmp_path,
        checkpoints_list=[
            {
                "id": "cp1",
                "criterion": "first checkpoint",
                "status": "done",
                "done_at": "2026-08-07T00:00:00Z",
            },
            {
                "id": "cp2",
                "criterion": "second checkpoint",
                "status": "done",
                "done_at": "2026-08-07T00:01:00Z",
            },
        ],
    )

    assert sr.load_implement_checkpoint_trace(
        tmp_path, "s06", "T-036-session-checkpoint-resume"
    ) == []


def test_resume_from_checkpoint_points_to_first_pending(tmp_path: Path) -> None:
    sr = _load_resilience()
    make_mock_shard(
        tmp_path,
        checkpoints_list=[
            {"id": "cp1", "criterion": "first checkpoint", "status": "done"},
            {"id": "cp2", "criterion": "second checkpoint", "status": "pending"},
            {"id": "cp3", "criterion": "third checkpoint", "status": "pending"},
        ],
    )

    lines = sr.load_implement_checkpoint_trace(
        tmp_path, "s06", "T-036-session-checkpoint-resume"
    )

    assert "resume_from_checkpoint: cp2" in lines


def test_checkpoint_trace_skipped_not_resume_dirty(tmp_path: Path) -> None:
    sr = _load_resilience()
    make_mock_shard(tmp_path)
    sr.git_dirty_paths = lambda _cwd: []

    lines = sr.dirty_resume_prompt_lines(
        tmp_path,
        step_id="s06",
        plan_id="T-036-session-checkpoint-resume",
        last={"status": "completed"},
    )

    assert lines == []
    assert "## checkpoint_trace" not in lines


def test_flush_checkpoint_idempotent_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    shard = make_mock_shard(
        tmp_path,
        checkpoints_list=[
            {
                "id": "cp1",
                "criterion": "first checkpoint",
                "status": "done",
                "done_at": "2026-08-07T00:00:00Z",
            }
        ],
    )
    resolver = _load_epic_resolve()
    relative = shard.relative_to(tmp_path).as_posix()
    monkeypatch.setattr(
        sys,
        "argv",
        ["epic_resolve.py", "--cwd", str(tmp_path), "flush-checkpoint", "--path", relative, "--cp", "cp1"],
    )

    assert resolver.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert "already done" in result["error"]
    assert yaml.safe_load(shard.read_text(encoding="utf-8"))["checkpoints"][0]["status"] == "done"


def test_resume_dirty_block_unchanged(tmp_path: Path) -> None:
    sr = _load_resilience()
    sr.git_dirty_paths = lambda _cwd: ["memory-bank/back/implement/implement-T-036-session-checkpoint-resume/s06-checkpoint-resume.yaml"]

    lines = sr.dirty_resume_prompt_lines(
        tmp_path,
        step_id="s06",
        plan_id="T-036-session-checkpoint-resume",
        resume_from="s06",
        last={"status": "aborted", "reason": "interrupted"},
    )

    text = "\n".join(lines)
    assert "FORBIDDEN: discard/revert dirty step files" in text
    assert "REQUIRED: Read dirty_files first" in text


def test_flush_checkpoint_skips_decompose_shard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    shard = tmp_path / "memory-bank/back/plan/decompose-example/s05-checkpoint.yaml"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_text("schema: epic-decompose/v1\n", encoding="utf-8")
    resolver = _load_epic_resolve()
    relative = shard.relative_to(tmp_path).as_posix()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "epic_resolve.py",
            "--cwd",
            str(tmp_path),
            "flush-checkpoint",
            "--path",
            relative,
            "--cp",
            "cp1",
        ],
    )

    assert resolver.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["skipped"] is True
    assert "implement-only" in result["error"]


def test_cp_trace_extends_after_resume_dirty(tmp_path: Path) -> None:
    sr = _load_resilience()
    make_mock_shard(tmp_path)
    sr.git_dirty_paths = lambda _cwd: [
        "memory-bank/back/implement/implement-T-036-session-checkpoint-resume/s06-checkpoint-resume.yaml"
    ]

    lines = sr.dirty_resume_prompt_lines(
        tmp_path,
        step_id="s06",
        plan_id="T-036-session-checkpoint-resume",
        resume_from="s06",
        last={"status": "aborted"},
    )

    assert lines.index("## resume_dirty (HARD)") < lines.index("## checkpoint_trace (read-only)")


def _write_decompose_shard(tmp_path: Path) -> Path:
    plan_id = "T-036-session-checkpoint-resume"
    path = (
        tmp_path
        / "memory-bank/back/plan"
        / f"decompose-{plan_id}"
        / "s07-seed-test.yaml"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose/v1",
                "role": "back",
                "step_id": "s07",
                "plan_id": plan_id,
                "title": "seed implement test",
                "next_phase": "BACK IMPLEMENT",
                "goal": "create implement yaml early",
                "context": {"files": ["loop/context_loop.py"]},
                "checkpoints": [
                    {"id": "cp1", "criterion": "seed exists", "verify": "test -f x"},
                    {"id": "cp2", "criterion": "flush works", "verify": "test -f y"},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_seed_implement_creates_in_progress_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    dec = _write_decompose_shard(tmp_path)
    resolver = _load_epic_resolve()
    rel = dec.relative_to(tmp_path).as_posix()
    monkeypatch.setattr(
        sys,
        "argv",
        ["epic_resolve.py", "--cwd", str(tmp_path), "seed-implement", "--decompose", rel],
    )
    assert resolver.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["status"] == "in_progress"
    out = tmp_path / result["path"]
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert doc["schema"] == "epic-implement/v1"
    assert doc["status"] == "in_progress"
    assert [cp["status"] for cp in doc["checkpoints"]] == ["pending", "pending"]
    assert doc["resume_from"] == "cp1"
    assert "loop/context_loop.py" in doc["files"]

    monkeypatch.setattr(
        sys,
        "argv",
        ["epic_resolve.py", "--cwd", str(tmp_path), "seed-implement", "--decompose", rel],
    )
    assert resolver.main() == 0
    again = json.loads(capsys.readouterr().out)
    assert again["ok"] is True
    assert again["skipped"] is True


def test_seed_then_flush_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    dec = _write_decompose_shard(tmp_path)
    resolver = _load_epic_resolve()
    rel = dec.relative_to(tmp_path).as_posix()
    monkeypatch.setattr(
        sys,
        "argv",
        ["epic_resolve.py", "--cwd", str(tmp_path), "seed-implement", "--decompose", rel],
    )
    assert resolver.main() == 0
    seeded = json.loads(capsys.readouterr().out)
    impl_rel = seeded["path"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "epic_resolve.py",
            "--cwd",
            str(tmp_path),
            "flush-checkpoint",
            "--path",
            impl_rel,
            "--cp",
            "cp1",
        ],
    )
    assert resolver.main() == 0
    flushed = json.loads(capsys.readouterr().out)
    assert flushed["ok"] is True
    doc = yaml.safe_load((tmp_path / impl_rel).read_text(encoding="utf-8"))
    assert doc["checkpoints"][0]["status"] == "done"
    assert doc["checkpoints"][0].get("done_at")
    assert doc["checkpoints"][1]["status"] == "pending"