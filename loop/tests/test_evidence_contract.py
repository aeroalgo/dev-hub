from __future__ import annotations

import json
from pathlib import Path

from loop.kernel.cli import _bugfix_gate_paths
from loop.kernel.evidence import validate_runtime_evidence
from loop.kernel.index import bugfix_queue_intake, bugfix_queue_state, qa_pass_state


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _runtime_trace(*, command: str, timestamp: str = "2026-10-29T12:00:00Z") -> dict[str, object]:
    return {
        "schema": "runtime-http-evidence/v1",
        "status": "pass",
        "live_evidence": True,
        "evidence_type": "runtime_http",
        "timestamp": timestamp,
        "command": command,
        "exit_code": 0,
        "raw_http": {
            "service": {
                "headers": "HTTP/1.1 200 OK\n",
                "body": "{\"ok\":true}",
            }
        },
        "journeys": [{"name": "real HTTP journey", "status": "pass"}],
    }


def _queue(root: Path, *, item: str, verification: str, evidence_file: str = "") -> None:
    evidence_line = f"  evidence_file: {evidence_file}\n" if evidence_file else ""
    _write(
        root / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pass
  command: {verification!r}
  last_run_at: '2026-10-29T12:00:00Z'
  evidence: runtime command completed
{evidence_line}items:
  - id: BF-001
    status: done
    done_at: '2026-10-29T12:00:00Z'
    class: live_smoke
    title: real browser HTTP journey
    verify: timeout -k 10s 300s bash scripts/live_smoke.sh
    evidence: {item!r}
    evidence_file: {evidence_file!r}
""",
    )


def test_runtime_evidence_rejects_mock_trace_even_when_status_is_pass(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                **_runtime_trace(command="timeout bash scripts/live_smoke.sh"),
                "authorization_code": "mock_auth_code",
            }
        ),
        encoding="utf-8",
    )

    valid, reason = validate_runtime_evidence(
        tmp_path,
        "trace.json",
        expected_command="timeout bash scripts/live_smoke.sh",
        anchor="2026-10-29T12:00:00Z",
    )

    assert not valid
    assert reason == "runtime_evidence_synthetic"


def test_bugfix_intake_rejects_live_done_item_without_runtime_file(tmp_path: Path) -> None:
    _queue(
        tmp_path,
        item="HTTP 302 was observed in a static report",
        verification="bin/pytest -q",
    )

    valid, reason = bugfix_queue_intake(tmp_path, "back", "E1")

    assert not valid
    assert reason == "runtime_evidence_required"


def test_bugfix_state_accepts_matching_real_runtime_evidence(tmp_path: Path) -> None:
    command = "timeout -k 10s 300s bash scripts/live_smoke.sh"
    _write(
        tmp_path / "docs/reports/live.json",
        json.dumps(_runtime_trace(command=command)),
    )
    _queue(
        tmp_path,
        item="real HTTP response and redirect captured",
        verification=f"EVIDENCE_FILE=docs/reports/live.json {command}",
        evidence_file="docs/reports/live.json",
    )

    valid, reason = bugfix_queue_state(tmp_path, "back", "E1")

    assert valid
    assert reason == "bugfix_queue_ready"
    gate_paths, report_ready = _bugfix_gate_paths(tmp_path, "back", "E1")
    assert not report_ready
    assert tmp_path / "docs/reports/live.json" in gate_paths


def test_bugfix_state_rejects_stale_runtime_evidence(tmp_path: Path) -> None:
    command = "timeout -k 10s 300s bash scripts/live_smoke.sh"
    _write(
        tmp_path / "docs/reports/live.json",
        json.dumps(_runtime_trace(command=command, timestamp="2026-10-29T10:00:00Z")),
    )
    _queue(
        tmp_path,
        item="real HTTP response captured earlier",
        verification=f"EVIDENCE_FILE=docs/reports/live.json {command}",
        evidence_file="docs/reports/live.json",
    )
    queue_path = tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml"
    queue_path.write_text(
        queue_path.read_text(encoding="utf-8").replace(
            "2026-10-29T12:00:00Z", "2026-10-29T12:30:00Z"
        ),
        encoding="utf-8",
    )

    valid, reason = bugfix_queue_state(tmp_path, "back", "E1")

    assert not valid
    assert reason == "runtime_evidence_stale"


def test_qa_pass_rejects_browser_claim_without_typed_runtime_artifact(tmp_path: Path) -> None:
    _write(
        tmp_path / "memory-bank/back/qa/E1/qa-20261029-live.yaml",
        """schema: epic-qa/v1
verdict: pass
browser:
  status: pass
  journeys:
    - name: OAuth redirect
      status: pass
""",
    )

    valid, reason = qa_pass_state(tmp_path, "back", "E1")

    assert not valid
    assert reason == "qa_browser_evidence_required"


def test_qa_pass_accepts_browser_claim_with_real_runtime_trace(tmp_path: Path) -> None:
    command = "timeout -k 10s 300s bash scripts/live_smoke.sh"
    _write(
        tmp_path / "docs/reports/live.json",
        json.dumps(_runtime_trace(command=command)),
    )
    _write(
        tmp_path / "memory-bank/back/qa/E1/qa-20261029-live.yaml",
        """schema: epic-qa/v1
verdict: pass
browser:
  status: pass
  command: timeout -k 10s 300s bash scripts/live_smoke.sh
  evidence_file: docs/reports/live.json
  last_run_at: '2026-10-29T12:00:00Z'
  journeys:
    - name: OAuth redirect
      status: pass
""",
    )

    valid, reason = qa_pass_state(tmp_path, "back", "E1")

    assert valid
    assert reason == "runtime_evidence_valid"
