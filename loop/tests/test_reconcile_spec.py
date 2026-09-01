from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic.reconcile import (  # noqa: E402
    list_active_epic_ids,
    reconcile_epic,
    resolve_epic_bundle,
    run_reconcile_spec,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_tasks(active_ids: list[str]) -> str:
    rows = [
        "| ID | Title | Level | Step | Status | Progress |",
        "|----|-------|-------|------|--------|----------|",
    ]
    for eid in active_ids:
        rows.append(f"| {eid} | demo | L3 | IMPLEMENT | active | plan |")
    rows.append("| T-HUB-999 | queued | L3 | PLAN | queued | plan |")
    return "# Tasks\n\n## Active\n\n" + "\n".join(rows) + "\n"


def _seed_epic(tmp_path: Path, *, plan_id: str, as_built_path: str, create_file: bool) -> None:
    plan_root = tmp_path / "memory-bank" / "back" / "plan"
    dec_dir = plan_root / f"decompose-{plan_id}"
    dec_dir.mkdir(parents=True)
    _write(
        plan_root / f"plan-{plan_id}.md",
        f"# [{plan_id}] PLAN\n\n### Layout\n\n| Path | Action |\n|------|--------|\n"
        f"| `{as_built_path}` | Modify |\n",
    )
    shard = {
        "schema": "epic-decompose/v1",
        "role": "back",
        "step_id": "s01",
        "plan_id": plan_id,
        "title": "t",
        "next_phase": "BACK IMPLEMENT",
        "goal": "g",
        "context": {"files": [as_built_path]},
        "as_built": [as_built_path],
        "delta": [f"{as_built_path} ADD body"],
        "deletes": [],
        "out_of_scope": [],
        "checkpoints": [
            {"id": "cp1", "criterion": "c", "verify": "rg foo"},
            {"id": "cp2", "criterion": "c2", "verify": "rg bar"},
        ],
    }
    _write(dec_dir / "s01-demo.yaml", yaml.safe_dump(shard, allow_unicode=True, sort_keys=False))
    _write(
        dec_dir / "index.yaml",
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": plan_id,
                "steps": [
                    {
                        "id": "s01",
                        "file": "s01-demo.yaml",
                        "title": "t",
                        "next_phase": "BACK IMPLEMENT",
                        "status": "completed",
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
    )
    target = tmp_path / as_built_path
    if create_file:
        _write(target, "ok\n")


def test_list_active_epic_ids_reads_tasks_md(tmp_path: Path) -> None:
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks(["T-HUB-023", "T-HUB-017"]))
    assert list_active_epic_ids(tmp_path) == ["T-HUB-023", "T-HUB-017"]


def test_list_active_epic_ids_skips_queued(tmp_path: Path) -> None:
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks(["T-HUB-023"]))
    ids = list_active_epic_ids(tmp_path)
    assert "T-HUB-999" not in ids


def test_resolve_epic_bundle_finds_decompose_index(tmp_path: Path) -> None:
    plan_id = "T-HUB-904-demo"
    _seed_epic(tmp_path, plan_id=plan_id, as_built_path="src/a.py", create_file=True)
    bundle = resolve_epic_bundle(tmp_path, "T-HUB-904")
    assert bundle is not None
    assert bundle.plan_id == plan_id
    assert bundle.decompose_index.name == "index.yaml"


def test_stale_as_built_gives_rc001_high(tmp_path: Path) -> None:
    plan_id = "T-HUB-905-demo"
    _seed_epic(tmp_path, plan_id=plan_id, as_built_path="src/missing_as_built.py", create_file=False)
    bundle = resolve_epic_bundle(tmp_path, "T-HUB-905")
    assert bundle is not None
    res = reconcile_epic(tmp_path, bundle)
    finding_ids = [f["id"] for f in res["findings"]]
    assert "RC-001" in finding_ids
    rc001 = next(f for f in res["findings"] if f["id"] == "RC-001")
    assert rc001["severity"] == "HIGH"
    assert res["high_count"] >= 1


def test_reconcile_epic_stale_as_built_gives_rc001_high(tmp_path: Path) -> None:
    test_stale_as_built_gives_rc001_high(tmp_path)


def test_reconcile_plan_id_unknown_exit2(tmp_path: Path) -> None:
    res = run_reconcile_spec(tmp_path, plan_id="T-HUB-UNKNOWN")
    assert res["exit_code"] == 2
    assert "error" in res


def test_reconcile_active_epics_empty_tasks_exit0(tmp_path: Path) -> None:
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks([]))
    res = run_reconcile_spec(tmp_path)
    assert res["exit_code"] == 0
    assert res["findings_total"] == 0


def test_reconcile_readonly_does_not_mutate(tmp_path: Path) -> None:
    test_read_only_does_not_mutate_plan(tmp_path)


def test_read_only_does_not_mutate_plan(tmp_path: Path) -> None:
    plan_id = "T-HUB-902-demo"
    rel = "src/keep.py"
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks(["T-HUB-902"]))
    _seed_epic(tmp_path, plan_id=plan_id, as_built_path=rel, create_file=True)
    plan_file = tmp_path / "memory-bank/back/plan" / f"plan-{plan_id}.md"
    before = plan_file.read_text(encoding="utf-8")
    run_reconcile_spec(tmp_path)
    after = plan_file.read_text(encoding="utf-8")
    assert before == after


def test_cli_reconcile_spec_json(tmp_path: Path) -> None:
    plan_id = "T-HUB-903-demo"
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks([]))
    _seed_epic(tmp_path, plan_id=plan_id, as_built_path="src/x.py", create_file=True)
    cmd = [
        sys.executable,
        str(HOOKS / "epic_resolve.py"),
        "--cwd",
        str(tmp_path),
        "reconcile-spec",
        "--plan-id",
        "T-HUB-903",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["schema"] == "reconcile-report/v1"
    assert data["plan_id"] == plan_id


def test_cli_reconcile_spec_strict_exit1_on_high(tmp_path: Path) -> None:
    plan_id = "T-HUB-904-demo"
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks([]))
    _seed_epic(tmp_path, plan_id=plan_id, as_built_path="src/missing.py", create_file=False)
    cmd = [
        sys.executable,
        str(HOOKS / "epic_resolve.py"),
        "--cwd",
        str(tmp_path),
        "reconcile-spec",
        "--plan-id",
        "T-HUB-904",
        "--strict",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 1


def test_cli_reconcile_spec_unknown_plan_exit2(tmp_path: Path) -> None:
    _write(tmp_path / "memory-bank/tasks.md", _minimal_tasks([]))
    cmd = [
        sys.executable,
        str(HOOKS / "epic_resolve.py"),
        "--cwd",
        str(tmp_path),
        "reconcile-spec",
        "--plan-id",
        "T-HUB-999",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 2


def test_plan_template_has_appetite_section() -> None:
    plan_template = (ROOT / ".cursor/templates/plan.md").read_text(encoding="utf-8")
    assert "## Appetite" in plan_template
    assert "timebox_days" in plan_template
    assert "cut_list" in plan_template
    assert "max_steps" not in plan_template
    assert "circuit_breaker" not in plan_template


def test_decompose_index_template_appetite_optional() -> None:
    index_template = (ROOT / ".cursor/templates/decompose/index.yaml").read_text(encoding="utf-8")
    assert "# appetite:" in index_template
    assert "timebox_days" in index_template
    assert "max_steps" not in index_template
    assert "circuit_breaker" not in index_template


