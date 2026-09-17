from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cursor_pre_tool_use_denies_malformed_payload() -> None:
    hook = ROOT / ".cursor" / "hooks" / "pre_tool_use.py"
    result = subprocess.run(
        [sys.executable, str(hook)],
        input="not-json",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["permission"] == "deny"


def test_cursor_stop_hook_fails_when_no_test_runner_exists(tmp_path: Path) -> None:
    hook = ROOT / ".cursor" / "hooks" / "on_stop.py"
    payload = {"workspace_roots": [str(tmp_path)], "status": "completed"}
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    review = tmp_path / ".cursor" / "hooks-artifacts" / "review-request.md"
    assert "Код выхода тестов: `2`" in review.read_text(encoding="utf-8")
