from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_events import build_event, event_stream_digest, read_event_log_result  # noqa: E402


def _events(count: int = 21) -> list[dict[str, object]]:
    return [
        build_event(
            epic_id="demo",
            kind="qa_pass" if index % 2 else "bugfix_done",
            artifact=f"memory-bank/back/qa/event-{index}.yaml",
            artifact_sha256=hashlib.sha256(f"event-{index}".encode()).hexdigest(),
            seq=index,
            timestamp=f"2026-08-05T12:00:{index:02d}+00:00",
        )
        for index in range(1, count + 1)
    ]


def _write(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def test_replay_digest_is_independent_of_archive_split_and_file_order(tmp_path: Path) -> None:
    events = _events()
    baseline_path = tmp_path / "baseline/events.jsonl"
    baseline_path.parent.mkdir(parents=True)
    _write(baseline_path, events)
    baseline = read_event_log_result(baseline_path, expected_epic_id="demo", cwd=tmp_path)

    split_path = tmp_path / "split/events.jsonl"
    split_path.parent.mkdir(parents=True)
    _write(split_path, events[7:])
    _write(split_path.parent / "archive-z.jsonl", events[:7])
    split = read_event_log_result(split_path, expected_epic_id="demo", cwd=tmp_path)

    shuffled_path = tmp_path / "shuffled/events.jsonl"
    shuffled_path.parent.mkdir(parents=True)
    shuffled = list(events)
    random.Random(35).shuffle(shuffled)
    _write(shuffled_path, shuffled)
    shuffled_result = read_event_log_result(
        shuffled_path, expected_epic_id="demo", cwd=tmp_path
    )

    assert baseline.valid and split.valid and shuffled_result.valid
    assert event_stream_digest(baseline) == event_stream_digest(split)
    assert event_stream_digest(baseline) == event_stream_digest(shuffled_result)
    assert [event["seq"] for event in split.events] == list(range(1, 22))
