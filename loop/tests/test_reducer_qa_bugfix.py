from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))


def _load_epic_lib():
    path = ROOT / ".claude" / "hooks" / "epic_lib.py"
    spec = importlib.util.spec_from_file_location("epic_lib_reducer", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(cwd: Path, rel: str, body: str) -> Path:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_qa_fail_and_bugfix_done_reopen_current_qa(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    qa = _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: fail\n")

    failed = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert failed["phase"] == "QA"
    assert failed["reason_code"] == "qa_failed"
    assert failed["last_event"]["kind"] == "qa_fail"
    assert failed["last_seq"] == 1
    assert failed["diagnostics"] == []
    assert failed["event_digest"].startswith("sha256:")

    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-after-fail.md", "fixed\n")
    reopened_after_fail = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert reopened_after_fail["phase"] == "QA"
    assert reopened_after_fail["reason_code"] == "bugfix_reopens_qa"
    assert reopened_after_fail["last_event"]["kind"] == "bugfix_done"

    qa.write_text("verdict: pass\n", encoding="utf-8")
    passed = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert passed["phase"] == "DONE"
    assert passed["reason_code"] == "qa_passed"
    assert passed["last_event"]["kind"] == "qa_pass"
    assert passed["last_seq"] == 3

    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-current.md", "done\n")
    reopened = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert reopened["phase"] == "QA"
    assert reopened["reason_code"] == "bugfix_reopens_qa"
    assert reopened["last_event"]["kind"] == "bugfix_done"
    assert reopened["last_seq"] == 4
    assert reopened["expected_artifact"] == "memory-bank/back/qa/demo/qa-*.yaml"


def test_archive_qa_pass_is_not_terminal_after_later_revision(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    qa = _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-current.md", "done\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "QA"
    assert decision["reason_code"] == "bugfix_reopens_qa"
    assert decision["last_event"]["kind"] == "bugfix_done"
    assert decision["diagnostics"] == []
    assert decision["last_seq"] == 2
    assert decision["last_event"]["artifact"] != qa.relative_to(tmp_path).as_posix() or decision["phase"] == "QA"


def test_legacy_reflection_artifact_ignored_on_qa_fail(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: fail\n")
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "epic_id: demo\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "QA"
    assert decision["reason_code"] == "qa_failed"
    assert decision["last_event"]["kind"] == "qa_fail"
    assert decision["diagnostics"] == []


def test_bugfix_after_qa_pass_reopens_qa(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-late.md", "new fix\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "QA"
    assert decision["reason_code"] == "bugfix_reopens_qa"


def test_qa_pass_after_bugfix_advances_to_done(tmp_path: Path) -> None:
    """Bugfix after qa_pass reopens QA; a later qa_pass goes DONE."""
    lib = _load_epic_lib()
    qa = _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-late.md", "new fix\n")
    reopened = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert reopened["phase"] == "QA"
    assert reopened["reason_code"] == "bugfix_reopens_qa"

    qa.write_text("verdict: pass\nissues: []\n", encoding="utf-8")
    after_qa = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert after_qa["phase"] == "DONE"
    assert after_qa["reason_code"] == "qa_passed"
    assert after_qa["last_event"]["kind"] == "qa_pass"


def test_legacy_reflection_done_event_ignored(tmp_path: Path) -> None:
    """Historical reflection_done in event.log must not change phase or crash."""
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    first = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert first["phase"] == "DONE"
    events = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    assert events.is_file()
    next_seq = int(first["last_seq"]) + 1
    events.write_text(
        events.read_text(encoding="utf-8")
        + (
            '{"schema":"loop-event/v2","event_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
            f'"seq":{next_seq},"kind":"reflection_done",'
            '"artifact":"memory-bank/back/reflection/reflection-demo.md",'
            '"artifact_sha256":"'
            + ("b" * 64)
            + '","epic_id":"demo","epoch":0,'
            '"t":"2026-09-03T00:00:00+00:00","metadata":{}}\n'
        ),
        encoding="utf-8",
    )
    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert decision["phase"] == "DONE"
    assert decision["reason_code"] == "qa_passed"


def test_same_reconcile_orders_qa_after_bugfix(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-current.md", "fix\n")
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")

    kinds = [kind for kind, _path in lib._declared_artifacts(tmp_path, "back", "demo")]

    assert kinds == ["bugfix_done", "qa_pass"]
    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert decision["phase"] == "DONE"
    assert decision["reason_code"] == "qa_passed"
