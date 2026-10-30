from __future__ import annotations

import json
from pathlib import Path

from loop.diagnostics import capture_exception


def test_capture_exception_persists_context_and_redacts_secrets(
    tmp_path: Path,
    capsys,
) -> None:
    try:
        raise RuntimeError("request failed token=super-secret-value")
    except RuntimeError as exc:
        report = capture_exception(
            exc,
            operation="board_projection.update_card",
            project_root=tmp_path,
            context={
                "epic_id": "T-TEST-001",
                "webhook_url": "https://portal.example/rest/1/super-secret-hook/",
            },
        )

    assert report["schema"] == "loop-exception/v1"
    assert report["operation"] == "board_projection.update_card"
    assert report["error_id"]
    assert report["diagnostic_path"] == str(tmp_path / ".loop" / "diagnostics" / "last-exception.json")

    latest = json.loads(Path(report["diagnostic_path"]).read_text(encoding="utf-8"))
    journal = (tmp_path / ".loop" / "diagnostics" / "exceptions.jsonl").read_text(encoding="utf-8")
    serialized = json.dumps(latest, ensure_ascii=False) + journal
    assert "super-secret-value" not in serialized
    assert "super-secret-hook" not in serialized
    assert latest["context"]["epic_id"] == "T-TEST-001"
    assert "RuntimeError" in latest["exception"]["traceback"]
    assert report["error_id"] in capsys.readouterr().err
