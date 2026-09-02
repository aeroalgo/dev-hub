"""Tests for load_plan_section and mb-load --plan-section."""

import json
import subprocess
import sys

from loop.mb_load.plan_section import load_plan_section
from loop.mb_load.session import load_session


def test_load_section_happy(tmp_path):
    # Setup mock activeContext.md
    act_file = tmp_path / "memory-bank" / "activeContext.md"
    act_file.parent.mkdir(parents=True, exist_ok=True)
    act_file.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [foo.txt](foo.txt) — foo\n"
        "## Handoff BACK IMPLEMENT — s01\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")

    # Setup plan file
    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999-test-epic.md"
    plan_file.write_text(
        "# Plan Title\n\n"
        "## Section One\nContent for section 1\n\n"
        "## Section Two\nContent for section 2\n\n"
        "## Section Three\nContent for section 3\n\n"
        "## Section Four\nContent for section 4\n",
        encoding="utf-8",
    )

    content, err = load_plan_section(cwd=tmp_path, section=3)
    assert err is None
    assert content == "## Section Three\nContent for section 3"

    res = load_session(cwd=tmp_path, plan_section=3)
    assert res.ok is True
    plan_files = [f for f in res.files if f.path == "plan_section:3"]
    assert len(plan_files) == 1
    assert plan_files[0].content == "## Section Three\nContent for section 3"


def test_load_section_cli(tmp_path):
    act_file = tmp_path / "memory-bank" / "activeContext.md"
    act_file.parent.mkdir(parents=True, exist_ok=True)
    act_file.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [foo.txt](foo.txt) — foo\n"
        "## Handoff BACK IMPLEMENT — s01\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999-test-epic.md"
    plan_file.write_text(
        "## Section One\nContent for section 1\n\n"
        "## Section Two\nContent for section 2\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "harness/hooks/epic_resolve.py",
        "mb-load",
        "session",
        "--cwd",
        str(tmp_path),
        "--plan-section",
        "2",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    sec_files = [f for f in data["files"] if f["path"] == "plan_section:2"]
    assert len(sec_files) == 1
    assert sec_files[0]["content"] == "## Section Two\nContent for section 2"


def test_load_section_invalid_n(tmp_path):
    act_file = tmp_path / "memory-bank" / "activeContext.md"
    act_file.parent.mkdir(parents=True, exist_ok=True)
    act_file.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [foo.txt](foo.txt) — foo\n"
        "## Handoff BACK IMPLEMENT — s01\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999-test-epic.md"
    plan_file.write_text(
        "## Section One\nContent for section 1\n",
        encoding="utf-8",
    )

    content, err = load_plan_section(cwd=tmp_path, section=99)
    assert content is None
    assert err == "section_not_found"

    res = load_session(cwd=tmp_path, plan_section=99)
    assert res.ok is False
    assert "section_not_found" in res.diagnostic_codes


def test_load_section_plan_missing(tmp_path):
    act_file = tmp_path / "memory-bank" / "activeContext.md"
    act_file.parent.mkdir(parents=True, exist_ok=True)
    act_file.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [foo.txt](foo.txt) — foo\n"
        "## Handoff BACK IMPLEMENT — s01\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")

    content, err = load_plan_section(cwd=tmp_path, section=1)
    assert content is None
    assert err == "plan_missing"

    res = load_session(cwd=tmp_path, plan_section=1)
    assert res.ok is False
    assert "plan_missing" in res.diagnostic_codes


def test_section_content_no_bleed(tmp_path):
    act_file = tmp_path / "memory-bank" / "activeContext.md"
    act_file.parent.mkdir(parents=True, exist_ok=True)
    act_file.write_text(
        "---\n"
        "schema: loop-handoff/v1\n"
        "role: BACK\n"
        "mode: IMPLEMENT\n"
        "epic_id: T-HUB-999-test-epic\n"
        "step_id: s01\n"
        "---\n"
        "## load_now\n"
        "1. [foo.txt](foo.txt) — foo\n"
        "## Handoff BACK IMPLEMENT — s01\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")

    plan_dir = tmp_path / "memory-bank" / "back" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "plan-T-HUB-999-test-epic.md"
    plan_file.write_text(
        "## Section Three\nText in section 3\n\n"
        "## Section Four\nText in section 4\n",
        encoding="utf-8",
    )

    content, err = load_plan_section(cwd=tmp_path, section=1)
    assert err is None
    assert "Section Three" in content
    assert "Text in section 3" in content
    assert "Section Four" not in content
    assert "Text in section 4" not in content
