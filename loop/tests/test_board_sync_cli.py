from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from loop.board_sync.cli import main
from loop.board_sync.client import FakeClient

FIXTURES = Path(__file__).parent / "fixtures" / "board_sync"


def _dsh_home(tmp_path: Path, *, corrupt: bool = False) -> Path:
    project = tmp_path / "project"
    index = project / "memory-bank/back/plan/decompose-T-DEMO/index.yaml"
    index.parent.mkdir(parents=True)
    index.write_text(
        yaml.safe_dump(
            {
                "schema": "epic-decompose-index/v1",
                "plan_id": "T-DEMO",
                "steps": [
                    {"id": "s01", "title": "First pending", "status": "pending"},
                    {"id": "s02", "title": "Running", "status": "in_progress"},
                    {"id": "s03", "title": "Done", "status": "completed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (project / "memory-bank/back/plan/plan-T-DEMO.md").write_text(
        "# T-DEMO\n", encoding="utf-8"
    )
    (project / "memory-bank/back/plan/roadmap-epics.queue.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "roadmap-queue/v1",
                "role": "back",
                "queue": [
                    {"id": "T-DEMO", "plan": "plan-T-DEMO.md", "deps": []}
                ],
            }
        ),
        encoding="utf-8",
    )
    if corrupt:
        (project / "memory-bank/back/plan/roadmap-epics.queue.yaml").unlink()
    registry = tmp_path / "dsh" / "storages" / "workspace.json"
    registry.parent.mkdir(parents=True)
    if corrupt:
        registry.write_text("{not-json", encoding="utf-8")
    else:
        registry.write_text(
            json.dumps(
                {
                    "tables": {
                        "workspaces": {
                            "demo": {"path": str(project)},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
    return registry.parent.parent


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "sync" in output
    assert "status" in output


def test_dry_run_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    dsh_home = _dsh_home(tmp_path)

    assert main(["sync", "--dsh-home", str(dsh_home), "--dry-run"], client=client) == 0

    output = capsys.readouterr().out
    assert "upsert" in output
    assert "mb-demo-back-t-demo-s01" in output
    assert "archive mb-" not in output
    assert client.write_count == 0


def test_sync_workspace_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    dsh_home = _dsh_home(tmp_path)

    assert (
        main(
            [
                "sync",
                "--dsh-home",
                str(dsh_home),
                "--workspace-id",
                "missing",
            ],
            client=client,
        )
        == 0
    )

    assert client.write_count == 0
    assert "upsert=0" in capsys.readouterr().out


def test_corrupt_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()

    assert main(["sync", "--dsh-home", str(_dsh_home(tmp_path, corrupt=True))], client=client) != 0

    assert "invalid JSON" in capsys.readouterr().err


def test_status_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dsh_home = _dsh_home(tmp_path)
    ledger = tmp_path / "ledger.json"

    assert main(
        [
            "sync",
            "--dsh-home",
            str(dsh_home),
            "--offline-ledger",
            str(ledger),
        ]
    ) == 0
    assert main(["status", "--offline-ledger", str(ledger)]) == 0

    output = capsys.readouterr().out
    assert "generation=1" in output
    assert "upsert=3" in output
    assert "archive=0" in output
    assert "noop=0" in output


def test_roadmap_selection_failure_is_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dsh_home = _dsh_home(tmp_path)
    index = tmp_path / "project/memory-bank/back/plan/decompose-T-DEMO/index.yaml"
    payload = yaml.safe_load(index.read_text(encoding="utf-8"))
    payload["steps"] = [
        {**step, "status": "completed"} for step in payload["steps"]
    ]
    index.write_text(yaml.safe_dump(payload), encoding="utf-8")
    (index.parent.parent / "roadmap-epics.queue.yaml").unlink()

    result = main(["sync", "--dsh-home", str(dsh_home)], client=FakeClient())

    assert result != 0
    assert "queue_yaml_missing" in capsys.readouterr().err


def test_missing_dsh_home(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["sync", "--dsh-home", "/does/not/exist"], client=FakeClient()) != 0

    assert "DSH_HOME does not exist" in capsys.readouterr().err


def test_wrapper_is_executable() -> None:
    assert (Path(__file__).parents[2] / "bin" / "hub-board").stat().st_mode & 0o111
