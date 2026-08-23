from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import read_event_log_result  # noqa: E402


def _load_epic_lib():
    path = ROOT / ".claude" / "hooks" / "epic_lib.py"
    spec = importlib.util.spec_from_file_location("epic_lib_revision_reconciliation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_content_is_idempotent_and_changed_content_appends_revision(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    artifact = tmp_path / "memory-bank/back/qa/demo/qa-result.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("verdict: pass\n", encoding="utf-8")

    assert lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)
    assert not lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)

    artifact.write_text("verdict: fail\n", encoding="utf-8")
    assert lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)

    event_path = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    result = read_event_log_result(event_path, expected_epic_id="demo", cwd=tmp_path)
    assert len(result.events) == 2
    assert result.events[0]["artifact_sha256"] != result.events[1]["artifact_sha256"]
    assert result.events[1]["metadata"]["previous_artifact_sha256"] == result.events[0]["artifact_sha256"]


def test_missing_artifact_is_not_appended(tmp_path: Path) -> None:
    lib = _load_epic_lib()
    artifact = tmp_path / "memory-bank/back/qa/demo/missing.yaml"

    assert not lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)
    assert not (tmp_path / "memory-bank/back/events/demo/events.jsonl").exists()
