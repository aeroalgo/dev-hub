"""Tests for session_start payload bundle/fingerprint injection."""

import pytest
from unittest.mock import patch
from harness.hooks.epic.core import session_start_payload
from loop.mb_load.schemas import MbLoadResult, MbLoadFile, LoopHandoffMeta


def test_plan_md_body_absent_from_session_start_inject_and_path_only(monkeypatch, tmp_path):
    """TM-002 / US-001 / SC-002: existing 500+ line plan.md in load_now must NOT be inlined into additionalContext."""
    monkeypatch.setenv("EPIC_LOOP", "1")
    mb_dir = tmp_path / "memory-bank" / "back" / "plan" / "T-HUB-072-context-bundle-fail-closed" / "md"
    mb_dir.mkdir(parents=True, exist_ok=True)

    unique_sentence = "UNIQUE_PLAN_SENTENCE_LINE_50_SHOULD_NOT_LEAK_INTO_INJECT"
    lines = [f"Line {i}" for i in range(1, 50)] + [unique_sentence] + [f"Line {i}" for i in range(51, 550)]
    plan_text = "\n".join(lines) + "\n"
    plan_file = mb_dir / "plan.md"
    plan_file.write_text(plan_text, encoding="utf-8")

    act_content = f"""---
schema: loop-handoff/v1
role: BACK
mode: DECOMPOSE
epic_id: T-HUB-072-context-bundle-fail-closed
---

## load_now
1. [{plan_file.relative_to(tmp_path)}](memory-bank/back/plan/T-HUB-072-context-bundle-fail-closed/md/plan.md) — plan doc.

## Handoff BACK DECOMPOSE
- **Эпик:** T-HUB-072-context-bundle-fail-closed
"""
    (tmp_path / "memory-bank" / "activeContext.md").write_text(act_content, encoding="utf-8")

    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-HUB-072-context-bundle-fail-closed", "status": "running"}):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        # Path must be present in bundle list
        assert "plan.md" in ctx
        # Unique sentence from plan body must NOT be in additionalContext (fail-closed against full body dump)
        assert unique_sentence not in ctx
        # Instruction Read this path must be present for path-only markdown
        assert "- memory-bank/back/plan/T-HUB-072-context-bundle-fail-closed/md/plan.md" in ctx
        assert "Read this path" in ctx
        assert "sha256:" in ctx


def test_no_inject_without_epic_loop(monkeypatch):
    monkeypatch.delenv("EPIC_LOOP", raising=False)
    assert session_start_payload(".") is None


def test_inject_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp1234567890",
            files=[
                MbLoadFile(path="file1.txt", content="hello", size_bytes=5, sha256="abc", truncated=False)
            ]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        assert "additionalContext" in res
        assert res["additionalContext"].startswith("COMMAND: BACK IMPLEMENT\n")
        assert "HARD READ" in res["additionalContext"]
        assert "fp1234567890" in res["additionalContext"]
        assert "file1.txt" in res["additionalContext"]


def test_inject_load_fail_graceful(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=False,
            status="incomplete",
            diagnostic_codes=["missing_active_context"],
            shape_errors=["activeContext.md missing"]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        assert "additionalContext" in res
        assert "CONTEXT_INCOMPLETE" in res["additionalContext"]
        assert "missing_active_context" in res["additionalContext"]
        assert "HALT" in res["additionalContext"]


def test_session_start_required_missing_context_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=False,
            status="incomplete",
            required_missing=["path/to/required.yaml"],
            files=[MbLoadFile(path="leftover.txt", content="leftover content", size_bytes=10, sha256="123")]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "CONTEXT_INCOMPLETE" in ctx
        assert "missing_required:path/to/required.yaml" in ctx
        assert "HALT" in ctx
        assert "leftover content" not in ctx
        assert "Warning: bundle load failed" not in ctx


def test_session_start_does_not_inject_leftover_required_as_complete(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=False,
            status="incomplete",
            required_missing=["critical_shard.yaml"],
            files=[MbLoadFile(path="other.txt", content="some content", size_bytes=12, sha256="456")]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "CONTEXT_INCOMPLETE" in ctx
        assert "other.txt" not in ctx
        assert "some content" not in ctx
        assert "Один шаг → FINISH" not in ctx


def test_required_exception_typed_not_warning_success(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session", side_effect=ValueError("corrupted config")):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "CONTEXT_INCOMPLETE" in ctx
        assert "required_context_exception:ValueError" in ctx
        assert "HALT" in ctx
        assert "Warning" not in ctx
        assert "Один шаг → FINISH" not in ctx


def test_optional_only_miss_degrade_not_halt(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        mock_load.return_value = MbLoadResult(
            ok=True,
            status="complete",
            fingerprint="fp_opt",
            files=[MbLoadFile(path="file1.txt", content="content1", size_bytes=8, sha256="abc")],
            optional_missing=["optional_doc.md"]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "CONTEXT_INCOMPLETE" not in ctx
        assert "HALT" not in ctx
        assert "Degraded (optional missing): optional_doc.md" in ctx
        assert "fp_opt" in ctx
        assert "file1.txt" in ctx
        assert "content1" in ctx
        assert "Один шаг → FINISH" in ctx


def test_inject_large_bundle_no_content(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session") as mock_load:
        large_content = "a" * 20000
        mock_load.return_value = MbLoadResult(
            ok=True,
            fingerprint="fp_large",
            files=[
                MbLoadFile(path="large.txt", content=large_content, size_bytes=20000, sha256="xyz", truncated=False)
            ]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "fp_large" in ctx
        assert "large.txt" in ctx
        assert large_content not in ctx


def test_session_start_payload_codex_entrypoint_agents_md(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("EPIC_RUNTIME", "codex")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session", return_value=MbLoadResult(ok=True, fingerprint="fp1")):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "- runtime: `codex`" in ctx
        assert "- entrypoint: `AGENTS.md`" in ctx
        assert "CLAUDE.md" not in ctx


def test_session_start_payload_claude_entrypoint_claude_md(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("EPIC_RUNTIME", "claude")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session", return_value=MbLoadResult(ok=True, fingerprint="fp1")):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "- runtime: `claude-code`" in ctx
        assert "- entrypoint: `CLAUDE.md`" in ctx
        assert "AGENTS.md" not in ctx


def test_session_start_payload_passes_epic_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("EPIC_RUNTIME", "codex-cli")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session", return_value=MbLoadResult(ok=True, fingerprint="fp1")):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        assert "- runtime: `codex`" in ctx
        assert "- entrypoint: `AGENTS.md`" in ctx


def test_unknown_epic_runtime_fail_closed_or_documented(monkeypatch, tmp_path):
    monkeypatch.setenv("EPIC_LOOP", "1")
    monkeypatch.setenv("EPIC_RUNTIME", "unknown-runtime")
    with patch("harness.hooks.epic.core.load_epic_state", return_value={"active": "T-01", "status": "running"}), \
         patch("loop.mb_load.session.load_session", return_value=MbLoadResult(ok=True, fingerprint="fp1")):
        res = session_start_payload(tmp_path)
        assert res is not None
        ctx = res["additionalContext"]
        # Documented default for unknown runtime in prompt_builder is claude-code / CLAUDE.md
        assert "- runtime: `claude-code`" in ctx
        assert "- entrypoint: `CLAUDE.md`" in ctx

