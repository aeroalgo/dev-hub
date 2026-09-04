import json
import subprocess
import sys
from pathlib import Path
import pytest

from loop.paths.epic_layout import resolve, EpicLayoutKind


def _run_cli(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, dict]:
    root = Path(__file__).resolve().parents[3]
    cmd = [sys.executable, str(root / "harness" / "hooks" / "epic_resolve.py")] + args
    res = subprocess.run(
        cmd,
        cwd=cwd or root,
        env=env,
        capture_output=True,
        text=True,
    )
    data = {}
    if res.stdout.strip():
        try:
            data = json.loads(res.stdout)
        except Exception:
            pass
    return res.returncode, data


def test_cli_plan_dry_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    epic_id = "T-HUB-TEST"

    code, data = _run_cli(
        ["mb-scaffold", "plan", "--epic-id", epic_id, "--dry-run"],
        cwd=tmp_path,
    )
    assert code == 0
    assert data.get("ok") is True
    assert data.get("dry_run") is True
    assert len(data.get("created", [])) == 1

    # Files should not exist on dry-run
    plan_md = resolve("back", epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    assert not plan_md.exists()


def test_cli_plan_apply_and_force(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    epic_id = "T-HUB-TEST"

    code, data = _run_cli(
        ["mb-scaffold", "plan", "--epic-id", epic_id, "--title", "My Epic Plan"],
        cwd=tmp_path,
    )
    assert code == 0
    assert data.get("ok") is True
    assert len(data.get("created", [])) == 1

    plan_md = resolve("back", epic_id, EpicLayoutKind.PLAN_MD, project_root=tmp_path)
    assert plan_md.exists()
    assert not (plan_md.parent.parent / "yaml" / "plan.yaml").exists()
    assert "# Plan: My Epic Plan" in plan_md.read_text()

    # Re-run without force should fail
    code_dup, data_dup = _run_cli(
        ["mb-scaffold", "plan", "--epic-id", epic_id],
        cwd=tmp_path,
    )
    assert code_dup == 2
    assert data_dup.get("ok") is False
    assert "already exists" in data_dup.get("error", "")

    # Re-run with force should succeed
    code_force, data_force = _run_cli(
        ["mb-scaffold", "plan", "--epic-id", epic_id, "--force"],
        cwd=tmp_path,
    )
    assert code_force == 0
    assert data_force.get("ok") is True


def test_cwd_guard(tmp_path: Path, monkeypatch):
    """Calling mb-scaffold from an arbitrary directory without PROJECT_ROOT must exit 2 with cwd guard error."""
    # Ensure PROJECT_ROOT and DEV_HUB are not pointing to tmp_path
    monkeypatch.delenv("PROJECT_ROOT", raising=False)
    monkeypatch.delenv("DEV_HUB", raising=False)

    arbitrary_dir = tmp_path / "arbitrary_isolated_dir"
    arbitrary_dir.mkdir(parents=True, exist_ok=True)

    code, data = _run_cli(
        ["--cwd", str(arbitrary_dir), "mb-scaffold", "plan", "--epic-id", "T-HUB-TEST"],
        cwd=arbitrary_dir,
    )
    assert code == 2
    assert data.get("ok") is False
    assert "cwd guard violation" in data.get("error", "")


def test_cli_decompose_and_implement_all(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    epic_id = "T-HUB-TEST"

    # 1. Create plan first
    code_p, _ = _run_cli(
        ["mb-scaffold", "plan", "--epic-id", epic_id],
        cwd=tmp_path,
    )
    assert code_p == 0

    # 2. Decompose with formula fallback
    code_d, data_d = _run_cli(
        ["mb-scaffold", "decompose", "--epic-id", epic_id, "--formula", "hooks-epic"],
        cwd=tmp_path,
    )
    assert code_d == 0
    assert data_d.get("ok") is True
    assert len(data_d.get("created", [])) >= 3

    # 3. Implement all
    code_i, data_i = _run_cli(
        ["mb-scaffold", "implement", "--epic-id", epic_id, "--all"],
        cwd=tmp_path,
    )
    assert code_i == 0
    assert data_i.get("ok") is True
    assert len(data_i.get("created", [])) >= 1


def test_cli_qa_analyze_audit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    epic_id = "T-HUB-TEST"

    # QA
    code_qa, data_qa = _run_cli(
        ["mb-scaffold", "qa", "--epic-id", epic_id],
        cwd=tmp_path,
    )
    assert code_qa == 0
    assert data_qa.get("ok") is True

    # Analyze
    code_ana, data_ana = _run_cli(
        ["mb-scaffold", "analyze", "--epic-id", epic_id],
        cwd=tmp_path,
    )
    assert code_ana == 0
    assert data_ana.get("ok") is True

    # Audit
    code_aud, data_aud = _run_cli(
        ["mb-scaffold", "audit", "--epic-id", epic_id],
        cwd=tmp_path,
    )
    assert code_aud == 0
    assert data_aud.get("ok") is True
