"""Tests for episode packages wiring into context_loop (prepare_session & check_after)."""

from pathlib import Path
from unittest.mock import patch
import pytest

from loop.context_loop import prepare_session, check_after
from loop.episodes import episode_dir


AC_VALID_CONTENT_1 = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-001
step_id: s01
---
## load_now
1. [foo.md](memory-bank/foo.md)

## Handoff BACK IMPLEMENT s01
- next: s01
"""

AC_VALID_CONTENT_2 = """---
schema: loop-handoff/v1
role: BACK
mode: IMPLEMENT
epic_id: T-HUB-001
step_id: s01
---
## load_now
1. [foo.md](memory-bank/foo.md)

## Handoff BACK IMPLEMENT s01
- next: s01
- done step
"""


def test_prepare_session_has_episode_id(tmp_path: Path):
    """cp1: prepare_session returns dict with episode_id != None when activeContext exists."""
    ac_file = tmp_path / "memory-bank" / "activeContext.md"
    ac_file.parent.mkdir(parents=True, exist_ok=True)
    ac_file.write_text(
        AC_VALID_CONTENT_1,
        encoding="utf-8",
    )
    (tmp_path / "memory-bank" / "foo.md").write_text("foo", encoding="utf-8")

    res = prepare_session(tmp_path)
    assert res.get("ok") is True
    assert "episode_id" in res
    assert res["episode_id"] is not None
    assert isinstance(res["episode_id"], str)
    assert len(res["episode_id"]) > 0


def test_check_after_creates_manifest(tmp_path: Path):
    """cp2: check_after calls finalize_episode — episode dir created, manifest.json exists."""
    ac_file = tmp_path / "memory-bank" / "activeContext.md"
    ac_file.parent.mkdir(parents=True, exist_ok=True)
    ac_file.write_text(
        AC_VALID_CONTENT_1,
        encoding="utf-8",
    )
    (tmp_path / "memory-bank" / "foo.md").write_text("foo", encoding="utf-8")

    prep_res = prepare_session(tmp_path)
    assert prep_res.get("ok") is True
    ep_id = prep_res["episode_id"]

    # change activeContext slightly so fingerprint changes and check_after proceeds
    ac_file.write_text(
        AC_VALID_CONTENT_2,
        encoding="utf-8",
    )

    ca_res = check_after(tmp_path, fingerprint_before=prep_res["fingerprint"])
    assert ca_res.get("ok") is True
    assert ca_res.get("episode_id") == ep_id

    ep_path = episode_dir(tmp_path, ep_id)
    assert ep_path.is_dir()
    manifest_file = ep_path / "manifest.json"
    assert manifest_file.is_file()


def test_finalize_exception_does_not_block(tmp_path: Path):
    """cp3: finalize_episode exception does not block check_after (graceful degradation)."""
    ac_file = tmp_path / "memory-bank" / "activeContext.md"
    ac_file.parent.mkdir(parents=True, exist_ok=True)
    ac_file.write_text(
        AC_VALID_CONTENT_1,
        encoding="utf-8",
    )
    (tmp_path / "memory-bank" / "foo.md").write_text("foo", encoding="utf-8")

    prep_res = prepare_session(tmp_path)
    assert prep_res.get("ok") is True

    ac_file.write_text(
        AC_VALID_CONTENT_2,
        encoding="utf-8",
    )

    with patch("loop.context_loop.finalize_episode", side_effect=RuntimeError("disk error")):
        ca_res = check_after(tmp_path, fingerprint_before=prep_res["fingerprint"])
        assert ca_res.get("ok") is True


def test_tier0_check_after_finalizes(tmp_path: Path):
    """test_tier0_check_after_finalizes: _run_tier0_check_after also calls finalize."""
    from loop.context_loop import _run_tier0_check_after

    ac_file = tmp_path / "memory-bank" / "activeContext.md"
    ac_file.parent.mkdir(parents=True, exist_ok=True)
    ac_file.write_text(
        AC_VALID_CONTENT_1,
        encoding="utf-8",
    )
    (tmp_path / "memory-bank" / "foo.md").write_text("foo", encoding="utf-8")

    prep_res = prepare_session(tmp_path)
    assert prep_res.get("ok") is True
    ep_id = prep_res["episode_id"]

    res_input = {"ok": True, "complete": False}
    out_res = _run_tier0_check_after(tmp_path, res_input)
    assert out_res.get("episode_id") == ep_id

    ep_path = episode_dir(tmp_path, ep_id)
    assert (ep_path / "manifest.json").is_file()

