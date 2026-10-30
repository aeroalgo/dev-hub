from __future__ import annotations

import json
from pathlib import Path

from loop.kernel.cli import _bugfix_gate_paths, main
from loop.kernel.evidence import validate_runtime_evidence
from loop.kernel.index import (
    bugfix_queue_intake,
    bugfix_queue_state,
    phase_payload,
    qa_pass_state,
    sync_bugfix_queue_evidence,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _runtime_trace(
    *,
    command: str,
    timestamp: str = "2026-10-29T12:00:00Z",
    evidence_type: str = "runtime_http",
) -> dict[str, object]:
    return {
        "schema": "runtime-http-evidence/v1",
        "status": "pass",
        "live_evidence": True,
        "evidence_type": evidence_type,
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


def test_bugfix_state_rejects_anchor_mismatch_runtime_evidence(tmp_path: Path) -> None:
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
    assert reason == "runtime_evidence_anchor_mismatch"
    synced, sync_reason = sync_bugfix_queue_evidence(tmp_path, "back", "E1")
    assert not synced
    assert sync_reason == "runtime_evidence_stale"


def test_runtime_evidence_requires_anchor_within_fifteen_seconds(tmp_path: Path) -> None:
    command = "timeout -k 10s 300s bash scripts/live_smoke.sh"
    path = tmp_path / "docs/reports/live.json"
    _write(path, json.dumps(_runtime_trace(command=command, timestamp="2026-10-29T12:00:10Z")))

    ok_near, reason_near = validate_runtime_evidence(
        tmp_path,
        "docs/reports/live.json",
        expected_command=command,
        anchor="2026-10-29T12:00:00Z",
    )
    assert ok_near
    assert reason_near == "runtime_evidence_valid"

    _write(path, json.dumps(_runtime_trace(command=command, timestamp="2026-10-29T12:02:00Z")))
    ok_far, reason_far = validate_runtime_evidence(
        tmp_path,
        "docs/reports/live.json",
        expected_command=command,
        anchor="2026-10-29T12:00:00Z",
    )
    assert not ok_far
    assert reason_far == "runtime_evidence_anchor_mismatch"


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


def test_qa_pass_auto_syncs_rewritten_runtime_evidence_anchor(tmp_path: Path) -> None:
    command = "bash scripts/infra/compose_smoke.sh"
    evidence_path = "deploy/compose-smoke-evidence.json"
    _write(
        tmp_path / evidence_path,
        json.dumps(_runtime_trace(command=command, timestamp="2026-10-29T12:05:00Z")),
    )
    qa_path = tmp_path / "memory-bank/back/qa/E1/qa-20261029-live.yaml"
    _write(
        qa_path,
        f"""schema: epic-qa/v1
verdict: pass
live_smoke:
  status: pass
  command: {command}
  evidence_file: {evidence_path}
  last_run_at: '2026-10-29T12:00:00Z'
""",
    )

    valid, reason = qa_pass_state(tmp_path, "back", "E1")

    assert valid
    assert reason == "runtime_evidence_valid"
    payload = phase_payload(qa_path)
    assert payload is not None
    assert payload["live_smoke"]["last_run_at"] == "2026-10-29T12:05:00Z"


def test_app_qa_rejects_explicit_full_suite_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "memory-bank/app/qa/E1/qa-20261029-app.yaml",
        """schema: app-qa/v1
role: app
verdict: pass
suite_scope: full
""",
    )

    valid, reason = qa_pass_state(tmp_path, "app", "E1")

    assert not valid
    assert reason == "qa_suite_scope_app_lanes_required"


def test_app_qa_requires_suite_scope(tmp_path: Path) -> None:
    _write(
        tmp_path / "memory-bank/app/qa/E1/qa-20261029-app.yaml",
        """schema: app-qa/v1
role: app
verdict: pass
""",
    )

    valid, reason = qa_pass_state(tmp_path, "app", "E1")

    assert not valid
    assert reason == "qa_suite_scope_app_lanes_required"


def test_check_bugfix_queue_auto_syncs_closed_bugfix_anchors(tmp_path: Path, capsys) -> None:
    command = "python3 scripts/run_browser_qa.py"
    old_path = "docs/reports/bugfix-browser.json"
    _write(
        tmp_path / old_path,
        json.dumps(
            _runtime_trace(
                command=command,
                timestamp="2026-10-29T12:05:00Z",
                evidence_type="runtime_browser",
            )
        ),
    )
    _write(
        tmp_path / "memory-bank/app/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
role: app
verification:
  status: pass
  command: {command}
  last_run_at: '2026-10-29T12:00:00Z'
  evidence: targeted unit regression
  evidence_file: {old_path}
items:
  - id: BF-001
    status: done
    done_at: '2026-10-29T12:00:00Z'
    class: browser
    verify: {command!r}
    evidence_file: {old_path}
    evidence: browser regression captured
""",
    )
    _write(
        tmp_path / "memory-bank/app/qa/E1/qa-20261029-app.yaml",
        f"""schema: app-qa/v1
role: app
verdict: pass
suite_scope: app_lanes
browser:
  status: pass
  command: {command}
  evidence_file: {old_path}
  last_run_at: '2026-10-29T12:05:00Z'
  journeys:
    - name: login
      status: pass
""",
    )

    queue_before, queue_before_reason = bugfix_queue_state(tmp_path, "app", "E1")
    rc = main(
        [
            "check-bugfix-queue",
            "--project",
            str(tmp_path),
            "--role",
            "app",
            "--epic",
            "E1",
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    queue_after, queue_after_reason = bugfix_queue_state(tmp_path, "app", "E1")
    valid, reason = qa_pass_state(tmp_path, "app", "E1")

    assert not queue_before
    assert queue_before_reason == "runtime_evidence_anchor_mismatch"
    assert rc == 0
    assert output["reason"] == "bugfix_queue_ready"
    assert output["sync_reason"] == "bugfix_queue_anchors_synced"
    assert queue_after
    assert queue_after_reason == "bugfix_queue_ready"
    assert valid
    assert reason == "runtime_evidence_valid"


def test_compose_smoke_verification_uses_typed_timestamp_anchor(tmp_path: Path) -> None:
    command = "bash scripts/infra/compose_smoke.sh"
    evidence_path = "deploy/compose-smoke-evidence.json"
    _write(
        tmp_path / evidence_path,
        json.dumps(
            _runtime_trace(
                command=command,
                timestamp="2026-10-29T12:05:00Z",
            )
        ),
    )
    _write(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
verification:
  status: pass
  command: {command}
  last_run_at: '2026-10-29T12:00:00Z'
  evidence: compose smoke passed
  evidence_file: {evidence_path}
items:
  - id: BF-001
    status: done
    done_at: '2026-10-29T12:00:00Z'
    class: ac_gap
    verify: bin/pytest -q
    evidence: targeted regression passed
""",
    )

    valid, reason = bugfix_queue_state(tmp_path, "back", "E1")
    assert not valid
    assert reason == "runtime_evidence_anchor_mismatch"

    synced, sync_reason = sync_bugfix_queue_evidence(tmp_path, "back", "E1")

    assert synced
    assert sync_reason == "bugfix_queue_anchors_synced"
    payload = phase_payload(
        tmp_path / "memory-bank/back/bugfix/E1/bugfix-queue.yaml"
    )
    assert payload is not None
    assert payload["verification"]["last_run_at"] == "2026-10-29T12:05:00Z"
    assert bugfix_queue_state(tmp_path, "back", "E1") == (True, "bugfix_queue_ready")


def test_qa_new_runtime_artifact_keeps_closed_bugfix_evidence_valid(tmp_path: Path) -> None:
    command = "python3 scripts/run_browser_qa.py"
    old_path = "docs/reports/bugfix-browser.json"
    new_path = "docs/reports/qa-browser-20261029T120500Z.json"
    _write(
        tmp_path / old_path,
        json.dumps(
            _runtime_trace(
                command=command,
                timestamp="2026-10-29T12:00:00Z",
                evidence_type="runtime_browser",
            )
        ),
    )
    _write(
        tmp_path / new_path,
        json.dumps(
            _runtime_trace(
                command=command,
                timestamp="2026-10-29T12:05:00Z",
                evidence_type="runtime_browser",
            )
        ),
    )
    _write(
        tmp_path / "memory-bank/app/bugfix/E1/bugfix-queue.yaml",
        f"""schema: epic-bugfix-queue/v1
epic_id: E1
role: app
verification:
  status: pass
  command: bin/pytest -q
  last_run_at: '2026-10-29T12:00:00Z'
  evidence: targeted unit regression
items:
  - id: BF-001
    status: done
    done_at: '2026-10-29T12:00:00Z'
    class: browser
    verify: {command!r}
    evidence_file: {old_path}
    evidence: browser regression captured
""",
    )
    _write(
        tmp_path / "memory-bank/app/qa/E1/qa-20261029-app.yaml",
        f"""schema: app-qa/v1
role: app
verdict: pass
suite_scope: app_lanes
browser:
  status: pass
  command: {command}
  evidence_file: {new_path}
  last_run_at: '2026-10-29T12:05:00Z'
  journeys:
    - name: login
      status: pass
""",
    )

    queue_valid, queue_reason = bugfix_queue_state(tmp_path, "app", "E1")
    qa_valid, qa_reason = qa_pass_state(tmp_path, "app", "E1")

    assert queue_valid
    assert queue_reason == "bugfix_queue_ready"
    assert qa_valid
    assert qa_reason == "runtime_evidence_valid"
