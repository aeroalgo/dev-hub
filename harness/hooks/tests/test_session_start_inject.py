"""Tests for session_start payload bundle/fingerprint injection."""

import pytest
from unittest.mock import patch
from harness.hooks.epic.core import session_start_payload
from loop.mb_load.schemas import MbLoadResult, MbLoadFile, LoopHandoffMeta


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
            diagnostic_codes=["missing_active_context"],
            shape_errors=["activeContext.md missing"]
        )
        res = session_start_payload(tmp_path)
        assert res is not None
        assert "additionalContext" in res
        assert "Warning" in res["additionalContext"] or "missing_active_context" in res["additionalContext"]


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
