from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_finish_integrity_diagnostic_codes_are_exported() -> None:
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_lib

    assert epic_lib.INDEX_IMPLEMENT_CONFLICT == "index_implement_conflict"
    assert epic_lib.MARK_INDEX_MISSING == "mark_index_missing"
    assert (
        epic_lib.FINISH_INTEGRITY_DECOMPOSE_MISSING
        == "finish_integrity_decompose_missing"
    )


def test_epic_lib_facade_exports_runtime_contract() -> None:
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_lib
    from epic_lib import (
        _decompose_index_path,
        checkpoint_lifecycle,
        checkpoint_resume,
        extract_handoff_block,
        extract_load_now,
        finalize_step,
        fingerprint_context,
        gates_from_phase,
        halt_epic,
        index_yaml_path,
        load_decompose_steps_fail_closed,
        load_epic_state,
        load_index_yaml,
        mark_index_step_status,
        mirror_verify_verdict,
        parse_steps_from_md,
        read_active_context,
        session_start_payload,
        validate_active_context_shape,
        validate_finish_integrity,
    )

    assert all(
        callable(symbol)
        for symbol in (
            _decompose_index_path,
            checkpoint_lifecycle,
            checkpoint_resume,
            extract_handoff_block,
            extract_load_now,
            finalize_step,
            fingerprint_context,
            gates_from_phase,
            halt_epic,
            index_yaml_path,
            load_decompose_steps_fail_closed,
            load_epic_state,
            load_index_yaml,
            mark_index_step_status,
            mirror_verify_verdict,
            parse_steps_from_md,
            read_active_context,
            session_start_payload,
            validate_active_context_shape,
            validate_finish_integrity,
        )
    )
    assert epic_lib.FINISH_INTEGRITY_DIAGNOSTIC_CODES == frozenset(
        {
            "index_implement_conflict",
            "mark_index_missing",
            "finish_integrity_decompose_missing",
        }
    )


def test_runner_does_not_auto_mark_index() -> None:
    runner_sources = (
        (ROOT / "loop" / "context_loop.py").read_text(encoding="utf-8"),
        (ROOT / ".claude" / "hooks" / "stop-gate.py").read_text(encoding="utf-8"),
    )

    assert all("mark_index_step_status" not in source for source in runner_sources)
    assert all("auto_mark" not in source for source in runner_sources)
    assert all("auto-mark" not in source for source in runner_sources)


def test_ownership_policy_index_not_auto_marked() -> None:
    source = (ROOT / ".claude" / "hooks" / "epic_lib.py").read_text(
        encoding="utf-8"
    )

    assert "never auto-mark" in source
    assert "from epic import" in source
    assert "def mark_index_step_status(" not in source
    assert "finalize-step" in source or "finalize_step" in source


def _load_ctx():
    import importlib.util
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_lib():
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_lib

    return epic_lib


def _write(cwd: Path, rel: str, body: str) -> None:
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_validate_finish_integrity_mark_index_missing(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints: []\n",
    )

    result = lib.validate_finish_integrity(
        tmp_path, decompose=decompose, step_id="s01", require_verify_pass=True
    )

    assert result["ok"] is False
    assert result["diagnostic_codes"] == [lib.MARK_INDEX_MISSING]
    assert result["errors"]


def test_check_after_repairs_mark_index_missing(tmp_path: Path) -> None:
    import importlib.util
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    path = ROOT / "loop" / "context_loop.py"
    spec = importlib.util.spec_from_file_location("context_loop", path)
    ctx = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(ctx)

    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s01-a.yaml](back/plan/decompose-demo/s01-a.yaml)\n\n"
        "## Handoff\n- **Следующий:** BACK IMPLEMENT s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_decompose": "memory-bank/back/plan/decompose-demo/index.md"}\n',
    )

    result = ctx.check_after(tmp_path, fingerprint_before="stale-before")

    assert "mark_index_missing" not in (result.get("diagnostic_codes") or [])
    impl_text = (tmp_path / impl).read_text(encoding="utf-8")
    assert "status: in_progress" in impl_text
    assert "status: completed" not in impl_text


def test_validate_finish_integrity_index_implement_conflict(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | completed |\n",
    )

    result = lib.validate_finish_integrity(
        tmp_path, decompose=decompose, step_id="s01", require_verify_pass=True
    )

    assert result["ok"] is False
    assert result["diagnostic_codes"] == [lib.INDEX_IMPLEMENT_CONFLICT]


def test_prepare_session_repairs_false_index_completed(tmp_path: Path) -> None:
    ctx = _load_ctx()
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | completed |\n",
    )
    _write(tmp_path, "memory-bank/activeContext.md", "## load_now\n")
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        '{"armed_decompose": "' + decompose + '", "armed_step": "s01"}\n',
    )

    result = ctx.prepare_session(tmp_path)

    assert result["ok"] is True
    assert result.get("halt") is not True
    idx_text = (tmp_path / decompose).read_text(encoding="utf-8")
    assert "completed" not in idx_text.lower() or "pending" in idx_text.lower()


def test_validate_finish_integrity_returns_diagnostic_codes_list(tmp_path: Path) -> None:
    result = _load_lib().validate_finish_integrity(
        tmp_path, decompose=None, step_id="s01", require_verify_pass=True
    )

    assert isinstance(result["diagnostic_codes"], list)
    assert result["diagnostic_codes"] == ["invalid_arg"]


def test_validate_finish_integrity_missing_index_uses_decompose_missing(
    tmp_path: Path,
) -> None:
    result = _load_lib().validate_finish_integrity(
        tmp_path,
        decompose="memory-bank/back/plan/decompose-missing/index.yaml",
        step_id="s01",
        require_verify_pass=True,
    )

    assert result["ok"] is False
    assert result["diagnostic_codes"] == ["finish_integrity_decompose_missing"]


def test_validate_finish_integrity_cli_returns_nonzero_on_conflict(
    tmp_path: Path,
) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints: []\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "validate-finish-integrity",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostic_codes"] == ["mark_index_missing"]


def test_validate_finish_integrity_cli_is_detect_only(tmp_path: Path) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | completed |\n",
    )
    before = (tmp_path / decompose).read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "validate-finish-integrity",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert (tmp_path / decompose).read_text(encoding="utf-8") == before
    assert json.loads(result.stdout)["diagnostic_codes"] == [
        "index_implement_conflict"
    ]


def test_finalize_step_requires_verify_pass(tmp_path: Path) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-a.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done: []\nfiles: []\ntests: []\nintegration_check: []\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
            }
        )
        + "\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "finalize-step",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["diagnostic"] == "verify_pass_missing"
    assert payload["step_id"] == "s01"


def test_finalize_step_accepts_pass_when_session_id_cleared(
    tmp_path: Path,
) -> None:
    """Abort/rebuild may drop epic session_id; projection-bound PASS must finalize."""
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | pending |\n"
        "| **s02** | [s02-b.yaml](s02-b.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-a.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo one\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s02-b.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s02\nplan_id: demo\n"
        "title: demo two\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done:\n- did work\n"
        "files:\n- a.py\n"
        "tests:\n- '`timeout 300s .venv/bin/pytest -q` — PASS'\n"
        "integration_check:\n- ok\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s01-a.yaml](back/plan/decompose-demo/s01-a.yaml)\n\n"
        "## Handoff\n- **Следующий:** BACK IMPLEMENT s01\n",
    )
    evidence = {
        "schema_version": "hook-verdict/v1",
        "verdict": "PASS",
        "session_id": "claude-abort-retry-id",
        "epic_id": "demo",
        "role": "BACK",
        "step": "s01",
        "projection_hash": "hash-keep",
        "phase_epoch": "epoch-keep",
        "event_digest": "digest-1",
        "authority": "autonomous",
    }
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
                "role": "BACK",
                "session_id": None,
                "projection_hash": "hash-keep",
                "phase_epoch": "epoch-keep",
                "event_digest": "digest-1",
                "projection": {
                    "epic_id": "demo",
                    "role": "BACK",
                    "next_step": "s01",
                    "step": "s01",
                    "projection_hash": "hash-keep",
                    "phase_epoch": "epoch-keep",
                    "event_digest": "digest-1",
                    "session_id": None,
                },
                "last_verify_verdict": "PASS",
                "last_verify_evidence": evidence,
            }
        )
        + "\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "finalize-step",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["finalized"] is True
    assert payload["step_id"] == "s01"
    index_yaml = (
        tmp_path / "memory-bank/back/plan/decompose-demo/index.yaml"
    ).read_text(encoding="utf-8")
    assert "status: completed" in index_yaml
    state = json.loads(
        (tmp_path / ".claude/runtime/epic/state.json").read_text(encoding="utf-8")
    )
    assert state.get("last_verify_verdict") is None
    assert state.get("last_verify_evidence") is None


def test_finalize_step_rejects_pass_for_other_step(tmp_path: Path) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | completed |\n"
        "| **s02** | [s02-b.yaml](s02-b.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s02-b.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s02\nplan_id: demo\n"
        "title: demo two\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s02-b.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s02\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done:\n- did work\n"
        "files:\n- a.py\n"
        "tests:\n- '`timeout 300s .venv/bin/pytest -q` — PASS'\n"
        "integration_check:\n- ok\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s02",
                "last_verify_verdict": "PASS",
                "last_verify_evidence": {
                    "authority": "autonomous",
                    "verdict": "PASS",
                    "step": "s01",
                    "projection_hash": "h",
                    "phase_epoch": "e",
                    "session_id": "x",
                },
            }
        )
        + "\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "finalize-step",
            "--decompose",
            decompose,
            "--step",
            "s02",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["diagnostic"] == "verdict_wrong_step"


def test_finalize_step_syncs_index_and_active_context(tmp_path: Path) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | pending |\n"
        "| **s02** | [s02-b.yaml](s02-b.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-a.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo one\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s02-b.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s02\nplan_id: demo\n"
        "title: demo two\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/implement/implement-demo/s01-a.yaml",
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done: []\nfiles: []\ntests: []\nintegration_check: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s01-a.yaml](back/plan/decompose-demo/s01-a.yaml)\n\n"
        "## Handoff\n- **Следующий:** BACK IMPLEMENT s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
                "last_verify_verdict": "PASS",
                "last_verify_evidence": {
                    "authority": "manual",
                    "verdict": "PASS",
                },
            }
        )
        + "\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "finalize-step",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["finalized"] is True
    assert payload["step_id"] == "s01"
    assert payload["next_step"] == "s02"
    assert payload["verify_diagnostic"] == "manual_fallback_non_authoritative"

    index_yaml = (
        tmp_path / "memory-bank/back/plan/decompose-demo/index.yaml"
    ).read_text(encoding="utf-8")
    assert "id: s01" in index_yaml
    assert "status: completed" in index_yaml

    active_context = (tmp_path / "memory-bank/activeContext.md").read_text(
        encoding="utf-8"
    )
    assert "s02-b.yaml" in active_context
    assert "index.yaml" in active_context
    assert "](back/plan/decompose-demo/index.md)" not in active_context
    log = tmp_path / "memory-bank/tasks/log" / f"{date.today():%Y-%m}.md"
    assert log.is_file()
    assert "BACK IMPLEMENT s01" in log.read_text(encoding="utf-8")


def test_finalize_step_from_in_progress_sets_implement_and_index(
    tmp_path: Path,
) -> None:
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-a.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done:\n- did work\n"
        "files:\n- a.py\n"
        "tests:\n- '`timeout 300s .venv/bin/pytest -q` — PASS'\n"
        "integration_check:\n- ok\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s01-a.yaml](back/plan/decompose-demo/s01-a.yaml)\n\n"
        "## Handoff\n- **Следующий:** BACK IMPLEMENT s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
                "last_verify_verdict": "PASS",
                "last_verify_evidence": {
                    "authority": "manual",
                    "verdict": "PASS",
                },
            }
        )
        + "\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / ".claude" / "hooks" / "epic_resolve.py"),
            "--cwd",
            str(tmp_path),
            "finalize-step",
            "--decompose",
            decompose,
            "--step",
            "s01",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["finalized"] is True
    assert payload["implement_completed_by_finalize"] is True
    impl_text = (tmp_path / impl).read_text(encoding="utf-8")
    assert "status: completed" in impl_text
    index_yaml = (
        tmp_path / "memory-bank/back/plan/decompose-demo/index.yaml"
    ).read_text(encoding="utf-8")
    assert "status: completed" in index_yaml


def test_finalize_step_rolls_back_implement_when_index_mark_fails(
    tmp_path: Path, monkeypatch
) -> None:
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_lib

    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "# Index\n"
        "| step_id | title | next_phase | status |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| **s01** | [s01-a.yaml](s01-a.yaml) | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        "memory-bank/back/plan/decompose-demo/s01-a.yaml",
        "schema: epic-decompose/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nnext_phase: BACK IMPLEMENT\nneeds_creative: 'no'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  verify: pytest\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done:\n- did work\n"
        "files:\n- a.py\n"
        "tests:\n- '`timeout 300s .venv/bin/pytest -q` — PASS'\n"
        "integration_check:\n- ok\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
                "last_verify_verdict": "PASS",
                "last_verify_evidence": {
                    "authority": "manual",
                    "verdict": "PASS",
                },
            }
        )
        + "\n",
    )

    def _fail_mark(*_args, **_kwargs):
        return {"ok": False, "error": "forced_mark_fail", "step_id": "s01"}

    monkeypatch.setattr(epic_lib, "mark_index_step_status", _fail_mark)
    # finalize_step in epic.core imports mark_index_step_status from same module
    import epic.core as epic_core

    monkeypatch.setattr(epic_core, "mark_index_step_status", _fail_mark)

    result = epic_lib.finalize_step(tmp_path, decompose, "s01")

    assert result["ok"] is False
    assert result.get("rolled_back_implement") is True
    impl_text = (tmp_path / impl).read_text(encoding="utf-8")
    assert "status: in_progress" in impl_text
    assert "status: completed" not in impl_text


def test_prepare_session_repairs_mark_index_missing(tmp_path: Path) -> None:
    ctx = _load_ctx()
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | pending |\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\nimplement_index: x\ndate: '2026-08-09'\n"
        "checkpoints: []\n",
    )
    _write(
        tmp_path,
        "memory-bank/activeContext.md",
        "## load_now\n1. [s01-a.yaml](back/plan/decompose-demo/s01-a.yaml)\n\n"
        "## Handoff\n- **Следующий:** BACK IMPLEMENT s01\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "armed_decompose": decompose,
                "armed_step": "s01",
                "armed_epic": "demo",
            }
        )
        + "\n",
    )

    result = ctx.prepare_session(tmp_path, model="gpt")

    assert result.get("halt") is not True or "mark_index_missing" not in (
        result.get("diagnostic_codes") or []
    )
    impl_text = (tmp_path / impl).read_text(encoding="utf-8")
    assert "status: in_progress" in impl_text


def test_finalize_step_last_snn_calls_promote_if_ready(tmp_path: Path, monkeypatch) -> None:
    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic.core as epic_core

    decompose = "memory-bank/back/plan/decompose-demo/index.yaml"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "schema: epic-decompose-index/v1\nplan_id: demo\nsteps:\n- id: s01\n  file: s01-a.yaml\n  status: pending\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\nimplement_index: memory-bank/back/plan/decompose-demo/index.yaml\ndate: '2026-08-09'\n"
        "checkpoints:\n- id: cp1\n  criterion: ok\n  status: done\n"
        "done:\n- did work\n"
        "files:\n- a.py\n"
        "tests:\n- '`timeout 300s .venv/bin/pytest -q` — PASS'\n"
        "integration_check:\n- ok\n",
    )
    _write(
        tmp_path,
        ".claude/runtime/epic/state.json",
        json.dumps(
            {
                "active": True,
                "armed_epic": "demo",
                "armed_decompose": decompose,
                "armed_step": "s01",
                "last_verify_verdict": "PASS",
                "last_verify_evidence": {
                    "authority": "manual",
                    "verdict": "PASS",
                },
            }
        )
        + "\n",
    )

    called = []
    def dummy_promote(cwd, epic_id, role):
        called.append((str(cwd), epic_id, role))
        return {"ok": True, "promoted": True}

    import loop.epic_transition as et
    monkeypatch.setattr(et, "promote_if_ready", dummy_promote)

    res = epic_core.finalize_step(tmp_path, decompose, "s01")
    assert res["ok"] is True
    assert len(called) == 1
    assert res.get("promoted") == {"ok": True, "promoted": True}


def test_implement_verification_results_dict_coercion(tmp_path: Path) -> None:
    import sys

    hooks = str(ROOT / ".claude" / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    import epic_yaml as ey

    impl = tmp_path / "memory-bank/back/implement/implement-demo/s01-a.yaml"
    impl.parent.mkdir(parents=True)
    impl.write_text(
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: completed\ndate: '2026-09-02'\n"
        "done:\n- x\nfiles:\n- a.py\nintegration_check:\n- ok\n"
        "verification_results:\n"
        "- verdict: PASS\n  agent_id: verify-implement\n  step_id: s01\n"
        "  recorded_at: '2026-09-02T00:00:00Z'\n"
        "checkpoints:\n- id: cp1\n  criterion: x\n  status: done\n",
        encoding="utf-8",
    )

    doc = ey.load_implement(impl)
    assert doc.verification_results == ["s01: PASS (verify-implement @2026-09-02T00:00:00Z)"]
    assert ey.implement_completed(tmp_path, str(impl.relative_to(tmp_path)))


def test_validate_finish_integrity_with_repair_false_index(tmp_path: Path) -> None:
    lib = _load_lib()
    decompose = "memory-bank/back/plan/decompose-demo/index.md"
    impl = "memory-bank/back/implement/implement-demo/s01-a.yaml"
    _write(
        tmp_path,
        decompose,
        "| **s01** | a | BACK IMPLEMENT | completed |\n",
    )
    _write(
        tmp_path,
        impl,
        "schema: epic-implement/v1\nrole: back\nstep_id: s01\nplan_id: demo\n"
        "title: demo\nstatus: in_progress\ndate: '2026-09-02'\n"
        "done:\n- x\nfiles:\n- a.py\nintegration_check:\n- ok\n"
        "checkpoints:\n- id: cp1\n  criterion: x\n  status: done\n",
    )

    first = lib.validate_finish_integrity(
        tmp_path, decompose=decompose, step_id="s01", require_verify_pass=True
    )
    assert first["ok"] is False
    assert lib.INDEX_IMPLEMENT_CONFLICT in first["diagnostic_codes"]

    repaired = lib.validate_finish_integrity_with_repair(
        tmp_path, decompose=decompose, step_id="s01", require_verify_pass=True
    )
    assert repaired["ok"] is True
    assert repaired.get("repaired_false_index") == ["s01"]
    idx_text = (tmp_path / decompose).read_text(encoding="utf-8")
    assert "| **s01** | a | BACK IMPLEMENT | pending |" in idx_text
