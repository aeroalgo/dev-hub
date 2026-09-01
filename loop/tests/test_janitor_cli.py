import json
import subprocess
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPIC_RESOLVE = ROOT / ".claude" / "hooks" / "epic_resolve.py"


def test_janitor_scan_exit_zero():
    cmd = [sys.executable, str(EPIC_RESOLVE), "--cwd", str(ROOT), "janitor-scan"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0


def test_janitor_scan_schema_valid():
    cmd = [sys.executable, str(EPIC_RESOLVE), "--cwd", str(ROOT), "janitor-scan", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    assert data.get("schema") == "janitor-report/v1"
    assert "findings" in data
    assert "summary" in data


def test_janitor_scan_json_flag():
    cmd = [sys.executable, str(EPIC_RESOLVE), "--cwd", str(ROOT), "janitor-scan", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert proc.stdout.strip().startswith("{")
    assert json.loads(proc.stdout)


def test_janitor_gc_dry_run():
    cmd = [sys.executable, str(EPIC_RESOLVE), "--cwd", str(ROOT), "janitor-gc", "--dry-run"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Janitor GC" in proc.stdout


def test_janitor_gc_apply_refuses_non_whitelist(tmp_path):
    # Setup mock workspace with a non-whitelisted path issue
    mb = tmp_path / "memory-bank"
    mb.mkdir()
    (mb / "activeContext.md").write_text("## load_now\n", encoding="utf-8")

    from loop.janitor.gc import GcEngine, GcWhitelistError
    from loop.janitor.schema import JanitorFinding

    engine = GcEngine(tmp_path)
    finding = JanitorFinding(
        category="stale_decompose_shard",
        description="test non whitelist",
        target_path="some/non/whitelisted/path.txt",
        actionable=True,
    )
    with pytest.raises(GcWhitelistError):
        engine.apply_repair(finding, dry_run=False)
