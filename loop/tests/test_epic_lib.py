from __future__ import annotations

import importlib.util
import logging
import os
import re
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


def test_discover_epic_for_pipeline_returns_resolved_identity(monkeypatch) -> None:
    lib = _load_lib()
    identity = {
        "status": "resolved",
        "epic_id": "T-037-loop-gap-closure",
        "role": "BACK",
        "role_dir": "back",
        "decompose": "memory-bank/back/plan/decompose-T-037-loop-gap-closure/index.yaml",
    }
    monkeypatch.setattr(lib, "resolve_pipeline_identity", lambda _cwd: identity)

    assert lib.discover_epic_for_pipeline(Path("/tmp/project")) == {
        key: identity[key] for key in ("epic_id", "role", "role_dir", "decompose")
    }


def test_discover_epic_for_pipeline_returns_none_for_unresolved(monkeypatch) -> None:
    lib = _load_lib()
    monkeypatch.setattr(
        lib,
        "resolve_pipeline_identity",
        lambda _cwd: {"status": "identity_not_found"},
    )

    assert lib.discover_epic_for_pipeline(Path("/tmp/project")) is None


def test_rebuild_projection_logs_when_identity_is_missing(monkeypatch, tmp_path, caplog) -> None:
    lib = _load_lib()
    monkeypatch.setattr(lib, "discover_epic_for_pipeline", lambda _cwd: None)

    with caplog.at_level(logging.WARNING):
        state = lib.rebuild_epic_projection(tmp_path)

    assert state["projection"]["epic_id"] is None
    assert "epic identity unavailable" in caplog.text
    assert "code=identity_unresolved" in caplog.text


def test_reconcile_current_epic_events_logs_when_identity_is_missing(
    monkeypatch, tmp_path, caplog
) -> None:
    lib = _load_lib()
    monkeypatch.setattr(lib, "discover_epic_for_pipeline", lambda _cwd: None)

    with caplog.at_level(logging.WARNING):
        assert lib.reconcile_current_epic_events(tmp_path) == []

    assert "epic identity unavailable" in caplog.text
    assert "code=identity_unresolved" in caplog.text


def test_epic_complete_allowed_halts_when_identity_is_missing(
    monkeypatch, tmp_path, caplog
) -> None:
    lib = _load_lib()
    monkeypatch.setattr(lib, "discover_epic_for_pipeline", lambda _cwd: None)

    with caplog.at_level(logging.WARNING):
        result = lib.epic_complete_allowed(tmp_path)

    assert result["allowed"] is False
    assert result["phase"] is None
    assert "code=identity_unresolved" in caplog.text


def test_find_qa_pass_artifact_is_backward_compatible_alias() -> None:
    lib = _load_lib()

    assert lib.find_qa_pass_artifact is lib.latest_qa_pass_artifact_for_reference


def test_latest_qa_pass_artifact_docstring_is_reference_only() -> None:
    lib = _load_lib()

    assert "REFERENCE ONLY" in lib.latest_qa_pass_artifact_for_reference.__doc__
    assert "NOT a completion test" in lib.latest_qa_pass_artifact_for_reference.__doc__


def test_find_next_decompose_step_docstring_marks_legacy_fallback() -> None:
    lib = _load_lib()

    assert "LEGACY FALLBACK" in lib.find_next_decompose_step.__doc__


def test_reconcile_deterministic_sort_for_equal_mtime(tmp_path) -> None:
    lib = _load_lib()
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-037-loop-gap-closure"
    qa_dir.mkdir(parents=True)
    paths = [qa_dir / "qa-20260806-b.yaml", qa_dir / "qa-20260806-a.yaml"]
    for path in paths:
        path.write_text("verdict: pass\n", encoding="utf-8")
        os.utime(path, ns=(1_000_000_000, 1_000_000_000))

    records = lib._declared_artifacts(tmp_path, "back", "T-037-loop-gap-closure")

    assert [path for _kind, path in records] == sorted(paths, key=lambda path: str(path))
    assert records == lib._declared_artifacts(tmp_path, "back", "T-037-loop-gap-closure")


def test_reconcile_sort_ignores_mtime_order(tmp_path) -> None:
    lib = _load_lib()
    qa_dir = tmp_path / "memory-bank" / "back" / "qa" / "T-037-loop-gap-closure"
    qa_dir.mkdir(parents=True)
    older = qa_dir / "qa-20260806-z.yaml"
    newer = qa_dir / "qa-20260806-a.yaml"
    older.write_text("verdict: pass\n", encoding="utf-8")
    newer.write_text("verdict: pass\n", encoding="utf-8")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

    records = lib._declared_artifacts(tmp_path, "back", "T-037-loop-gap-closure")

    assert [path for _kind, path in records] == [newer, older]


def test_post_implement_audit_handoff_has_no_standalone_epic_done(tmp_path) -> None:
    lib = _load_lib()
    body = lib.build_post_implement_active_context(
        role="BACK",
        role_dir="back",
        epic_id="T-003",
        tracker_rel="memory-bank/back/plan/decompose-T-003/index.yaml",
        tracker_link="back/plan/decompose-T-003/index.yaml",
        index_rel="memory-bank/back/plan/decompose-T-003/index.md",
        hub_rel=None,
        phase="AUDIT",
        qa_path=None,
        reflection_path=None,
        cwd=tmp_path,
    )
    assert "## Handoff BACK AUDIT" in body
    from epic.core import post_implement_handoff_violates_epic_done

    assert post_implement_handoff_violates_epic_done("AUDIT", body) is False


def test_post_implement_unknown_phase_has_no_standalone_epic_done(tmp_path) -> None:
    lib = _load_lib()
    body = lib.build_post_implement_active_context(
        role="BACK",
        role_dir="back",
        epic_id="T-003",
        tracker_rel="memory-bank/back/plan/decompose-T-003/index.yaml",
        tracker_link="back/plan/decompose-T-003/index.yaml",
        index_rel="memory-bank/back/plan/decompose-T-003/index.md",
        hub_rel=None,
        phase="WEIRD",
        qa_path=None,
        reflection_path=None,
        cwd=tmp_path,
    )
    from epic.core import post_implement_handoff_violates_epic_done

    assert post_implement_handoff_violates_epic_done("WEIRD", body) is False
    assert "Handoff BACK WEIRD" in body


def test_post_implement_done_keeps_standalone_epic_done(tmp_path) -> None:
    lib = _load_lib()
    body = lib.build_post_implement_active_context(
        role="BACK",
        role_dir="back",
        epic_id="T-003",
        tracker_rel="memory-bank/back/plan/decompose-T-003/index.yaml",
        tracker_link="back/plan/decompose-T-003/index.yaml",
        index_rel="memory-bank/back/plan/decompose-T-003/index.md",
        hub_rel=None,
        phase="DONE",
        qa_path=None,
        reflection_path=None,
        cwd=tmp_path,
    )
    from epic.core import post_implement_handoff_violates_epic_done

    assert post_implement_handoff_violates_epic_done("DONE", body) is False
    assert re.search(r"(?m)^EPIC_DONE\s*$", body)




def test_post_implement_done_forbids_archive_in_loop(tmp_path) -> None:
    lib = _load_lib()
    body = lib.build_post_implement_active_context(
        role="BACK",
        role_dir="back",
        epic_id="T-003",
        tracker_rel="memory-bank/back/plan/decompose-T-003/index.yaml",
        tracker_link="back/plan/decompose-T-003/index.yaml",
        index_rel="memory-bank/back/plan/decompose-T-003/index.md",
        hub_rel=None,
        phase="DONE",
        qa_path=None,
        reflection_path=None,
        cwd=tmp_path,
    )
    assert re.search(r"(?m)^EPIC_DONE\s*$", body)
    assert "ARCHIVE NOW / VAN в loop" in body or "FORBIDDEN:** ARCHIVE" in body or "FORBIDDEN: ARCHIVE" in body
    assert "await VAN" not in body
