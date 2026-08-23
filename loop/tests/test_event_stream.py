from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import build_event, read_event_log_result  # noqa: E402


def _event(epic_id: str, seq: int) -> dict[str, object]:
    artifact = f"memory-bank/back/qa/{epic_id}-{seq}.yaml"
    return build_event(
        epic_id=epic_id,
        kind="qa_pass",
        artifact=artifact,
        artifact_sha256=hashlib.sha256(artifact.encode()).hexdigest(),
        seq=seq,
        timestamp=f"2026-08-05T12:00:{seq:02d}+00:00",
    )


def _write(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def test_append_allocates_after_archived_highest_sequence(tmp_path: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("epic_lib_event_stream", ROOT / ".claude/hooks/epic_lib.py")
    assert spec and spec.loader
    lib = module_from_spec(spec)
    spec.loader.exec_module(lib)

    for index in range(21):
        artifact = tmp_path / f"memory-bank/back/qa/event-{index}.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"verdict: pass {index}\n", encoding="utf-8")
        assert lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)

    event_path = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    result = read_event_log_result(event_path, expected_epic_id="demo", cwd=tmp_path)
    assert [event["seq"] for event in result.events] == list(range(1, 22))
    assert result.archive_count == 1


def test_archive_reader_sorts_and_reports_sequence_collisions_and_gaps(tmp_path: Path) -> None:
    event_path = tmp_path / "events/demo/events.jsonl"
    event_path.parent.mkdir(parents=True)
    first, second, third = _event("demo", 1), _event("demo", 2), _event("demo", 3)
    _write(event_path.parent / "archive-z.jsonl", [third, first])
    _write(event_path.parent / "archive-a.jsonl", [first])
    _write(event_path, [third])

    result = read_event_log_result(event_path, expected_epic_id="demo", cwd=tmp_path)

    assert [event["seq"] for event in result.events] == [1, 3]
    assert result.collision_count == 2
    assert result.gap_count == 1
    assert {item.code for item in result.diagnostics} >= {"sequence_collision", "sequence_gap"}
    assert not result.valid


def test_append_refuses_existing_gap_or_collision(tmp_path: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("epic_lib_event_stream_refuse", ROOT / ".claude/hooks/epic_lib.py")
    assert spec and spec.loader
    lib = module_from_spec(spec)
    spec.loader.exec_module(lib)

    event_path = tmp_path / "memory-bank/back/events/demo/events.jsonl"
    event_path.parent.mkdir(parents=True)
    _write(event_path, [_event("demo", 2)])
    artifact = tmp_path / "memory-bank/back/qa/new.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("verdict: pass\n", encoding="utf-8")

    assert not lib._append_event(tmp_path, "back", "demo", "qa_pass", artifact)
    assert json.loads(event_path.read_text().splitlines()[0])["seq"] == 2
