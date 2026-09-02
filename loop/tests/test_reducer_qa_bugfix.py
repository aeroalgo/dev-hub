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
    assert passed["phase"] == "REFLECT"
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


def test_reflection_requires_current_qa_pass(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: fail\n")
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "epic_id: demo\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "QA"
    assert decision["reason_code"] == "qa_failed"
    assert decision["last_event"]["kind"] == "reflection_done"
    assert decision["diagnostics"] == []


def test_bugfix_evidence_before_reflection_does_not_block_done(tmp_path: Path) -> None:
    """Evidence rehash after qa_pass must not reopen once reflection exists."""
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-current.md", "evidence\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "epic_id: demo\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "DONE"
    assert decision["reason_code"] == "reflection_completed"


def test_bugfix_after_reflection_reopens_qa(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    _write(tmp_path, "memory-bank/back/reflection/reflection-demo.md", "epic_id: demo\n")
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-late.md", "new fix\n")

    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")

    assert decision["phase"] == "QA"
    assert decision["reason_code"] == "bugfix_reopens_qa"


def test_qa_pass_after_post_reflection_bugfix_advances_to_reflect(
    tmp_path: Path,
) -> None:
    """Post-reflection bugfix reopens QA; a later qa_pass must not pin QA forever."""
    lib = _load_epic_lib()
    qa = _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")
    refl = _write(
        tmp_path,
        "memory-bank/back/reflection/reflection-demo.md",
        "epic_id: demo\n",
    )
    lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-late.md", "new fix\n")
    reopened = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert reopened["phase"] == "QA"
    assert reopened["reason_code"] == "bugfix_reopens_qa"

    qa.write_text("verdict: pass\nissues: []\n", encoding="utf-8")
    after_qa = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert after_qa["phase"] == "REFLECT"
    assert after_qa["reason_code"] == "qa_passed_stale_reflection"
    assert after_qa["last_event"]["kind"] == "qa_pass"

    refl.write_text("epic_id: demo\nupdated after re-qa\n", encoding="utf-8")
    done = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert done["phase"] == "DONE"
    assert done["reason_code"] == "reflection_completed"


def test_same_reconcile_orders_qa_after_bugfix(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    _write(tmp_path, "memory-bank/back/bugfix/demo/bugfix-current.md", "fix\n")
    _write(tmp_path, "memory-bank/back/qa/demo/qa-current.yaml", "verdict: pass\n")

    kinds = [kind for kind, _path in lib._declared_artifacts(tmp_path, "back", "demo")]

    assert kinds == ["bugfix_done", "qa_pass"]
    decision = lib.reduce_epic_lifecycle(tmp_path, "back", "demo")
    assert decision["phase"] == "REFLECT"
    assert decision["reason_code"] == "qa_passed"