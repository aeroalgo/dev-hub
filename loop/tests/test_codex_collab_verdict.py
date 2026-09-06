"""Tests for Codex collab spawn verdict mirroring."""

from __future__ import annotations

import json
from pathlib import Path

from loop.codex_collab_verdict import (
    iter_codex_collab_verdicts,
    mirror_codex_collab_verdicts_from_log,
)


def _ensure_gate_agents(cwd: Path, *names: str) -> None:
    agents = cwd / ".claude" / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = agents / f"{name}.md"
        if not path.is_file():
            path.write_text(
                "---\n"
                f"name: {name}\n"
                "overlay:\n"
                "  managed: true\n"
                "  mode: gate\n"
                "  requires_model: true\n"
                "  default_loop: true\n"
                "  default_chat: false\n"
                "  verdict: pass-fail\n"
                "  allow_worktree: false\n"
                "---\nbody\n",
                encoding="utf-8",
            )


def test_iter_codex_collab_verdicts_json_fence() -> None:
    log = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "spawn-1",
                        "type": "collab_tool_call",
                        "tool": "spawn_agent",
                        "receiver_thread_ids": ["thread-a"],
                        "prompt": "Проведи pre-FINISH gate. @verify-implement. Не редактируй файлы.",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "wait-1",
                        "type": "collab_tool_call",
                        "tool": "wait",
                        "agents_states": {
                            "thread-a": {
                                "status": "completed",
                                "message": (
                                    "AC+ ok.\n\n"
                                    "```json\n"
                                    '{"schema":"loop-gate-verdict/v1",'
                                    '"agent_id":"verify-implement",'
                                    '"verdict":"PASS",'
                                    '"step_id":"s05",'
                                    '"session_id":"test-session",'
                                    '"epic_id":"T-HUB-044",'
                                    '"recorded_at":"2026-09-02T00:00:00Z"}\n'
                                    "```"
                                ),
                            }
                        },
                    },
                }
            ),
        ]
    )
    events = list(iter_codex_collab_verdicts(log))
    assert len(events) == 1
    assert events[0].agent_type == "verify-implement"
    assert events[0].verdict == "PASS"


def test_iter_codex_collab_verdicts_qa_json_without_at_mention() -> None:
    """Real QA shape: no @verify-qa in spawn prompt; agent_id only in JSON fence."""
    log = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "spawn-1",
                        "type": "collab_tool_call",
                        "tool": "spawn_agent",
                        "receiver_thread_ids": ["thread-qa"],
                        "prompt": (
                            "BACK QA review for epic T-HUB-044. Read-only; "
                            "do not invent a pass."
                        ),
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "wait-1",
                        "type": "collab_tool_call",
                        "tool": "wait",
                        "agents_states": {
                            "thread-qa": {
                                "status": "completed",
                                "message": (
                                    "QA verdict: FAIL.\n\n"
                                    "```json\n"
                                    "{\n"
                                    '  "schema": "loop-gate-verdict/v1",\n'
                                    '  "agent_id": "verify-qa",\n'
                                    '  "verdict": "FAIL",\n'
                                    '  "step_id": "QA",\n'
                                    '  "session_id": "test-session",\n'
                                    '  "epic_id": "T-HUB-044",\n'
                                    '  "recorded_at": "2026-09-02T00:00:00Z"\n'
                                    "}\n"
                                    "```"
                                ),
                            }
                        },
                    },
                }
            ),
        ]
    )
    events = list(iter_codex_collab_verdicts(log))
    assert len(events) == 1
    assert events[0].agent_type == "verify-qa"
    assert events[0].verdict == "FAIL"


def test_codex_collab_extra_field_invalid() -> None:
    """TM-005 QA / US-005 / SC-005 / AC+5 / AC−2 / FR-008: collab fence with extra field must be rejected."""
    log = "\n".join(
        [
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "spawn-1",
                        "type": "collab_tool_call",
                        "tool": "spawn_agent",
                        "receiver_thread_ids": ["thread-a"],
                        "prompt": "Run @verify-implement checks.",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "wait-1",
                        "type": "collab_tool_call",
                        "tool": "wait",
                        "agents_states": {
                            "thread-a": {
                                "status": "completed",
                                "message": (
                                    "```json\n"
                                    "{\n"
                                    '  "schema": "loop-gate-verdict/v1",\n'
                                    '  "agent_id": "verify-implement",\n'
                                    '  "verdict": "PASS",\n'
                                    '  "recorded_at": "2026-09-02T00:00:00Z",\n'
                                    '  "extra_unauthorized_field": "exploit"\n'
                                    "}\n"
                                    "```"
                                ),
                            }
                        },
                    },
                }
            ),
        ]
    )
    events = list(iter_codex_collab_verdicts(log))
    assert len(events) == 0


def test_no_collab_extra_ignore_after_purge() -> None:
    """s06 TDD: Ensure extra=ignore is purged from collab gate fence model."""
    from loop.schemas.gate_verdict import GateVerdictRecord
    assert GateVerdictRecord.model_config.get("extra") == "forbid"


def test_collab_fence_uses_canonical_parser() -> None:
    """FR-008: collab parsing calls canonical validate_boundary (extra=forbid, schema required)."""
    from loop.codex_collab_verdict import _parse_gate_verdict_fence
    bad_extra_msg = (
        "```json\n"
        '{"schema":"loop-gate-verdict/v1","agent_id":"verify-implement","verdict":"PASS","recorded_at":"2026-09-02T00:00:00Z","extra_field":123}\n'
        "```"
    )
    assert _parse_gate_verdict_fence(bad_extra_msg) is None


def test_iter_codex_collab_verdicts_prose_verdict_ignored() -> None:
    log = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "id": "wait-1",
                "type": "collab_tool_call",
                "tool": "wait",
                "agents_states": {
                    "thread-a": {
                        "status": "completed",
                        "message": "VERDICT: PASS\n",
                    }
                },
            },
        }
    )
    assert list(iter_codex_collab_verdicts(log)) == []


def test_mirror_codex_collab_verdicts_updates_epic_state(tmp_path: Path) -> None:
    _ensure_gate_agents(tmp_path, "verify-implement", "gate-repair")
    decompose_dir = tmp_path / "memory-bank" / "back" / "plan" / "decompose-T-HUB-044"
    decompose_dir.mkdir(parents=True, exist_ok=True)
    (decompose_dir / "index.yaml").write_text(
        "schema: epic-decompose-index/v1\n"
        "plan_id: T-HUB-044\n"
        "steps:\n"
        "- id: s05\n"
        "  file: s05.yaml\n"
        "  status: in_progress\n",
        encoding="utf-8",
    )
    implement_dir = tmp_path / "memory-bank" / "back" / "implement" / "implement-T-HUB-044"
    implement_dir.mkdir(parents=True, exist_ok=True)
    (implement_dir / "s05.yaml").write_text(
        "schema: epic-implement/v1\n"
        "role: back\n"
        "step_id: s05\n"
        "plan_id: T-HUB-044\n"
        "title: s05 test\n"
        "date: '2026-09-02'\n"
        "status: in_progress\n"
        "done:\n"
        "- done\n"
        "files: []\n"
        "tests:\n"
        "- '`true`'\n"
        "integration_check:\n"
        "- ok\n"
        "gaps:\n"
        "  status: none\n"
        "checkpoints:\n"
        "- id: cp1\n"
        "  criterion: ok\n"
        "  status: done\n",
        encoding="utf-8",
    )

    epic_dir = tmp_path / ".claude" / "runtime" / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    (epic_dir / "state.json").write_text(
        json.dumps(
            {
                "schema_version": "loop-state/v2",
                "active": True,
                "status": "running",
                "session_id": "codex-test-session",
                "armed_step": "s05",
                "armed_epic": "T-HUB-044",
                "armed_decompose": "memory-bank/back/plan/decompose-T-HUB-044/index.yaml",
                "projection": {
                    "epic_id": "T-HUB-044",
                    "role": "BACK",
                    "next_step": "s05",
                    "step": "s05",
                    "projection_hash": "sha256:test",
                    "phase_epoch": "sha256:test",
                    "event_digest": "sha256:test",
                },
            }
        ),
        encoding="utf-8",
    )

    log_path = tmp_path / "session.log"
    log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "spawn-1",
                            "type": "collab_tool_call",
                            "tool": "spawn_agent",
                            "receiver_thread_ids": ["thread-a"],
                            "prompt": "@verify-implement gate",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "wait-1",
                            "type": "collab_tool_call",
                            "tool": "wait",
                            "agents_states": {
                                "thread-a": {
                                    "status": "completed",
                                    "message": (
                                        "```json\n"
                                        '{"schema":"loop-gate-verdict/v1",'
                                        '"agent_id":"verify-implement",'
                                        '"verdict":"PASS",'
                                        '"step_id":"s05",'
                                        '"session_id":"codex-test-session",'
                                        '"epic_id":"T-HUB-044",'
                                        '"recorded_at":"2026-09-02T00:00:00Z"}\n'
                                        "```"
                                    ),
                                }
                            },
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    results = mirror_codex_collab_verdicts_from_log(
        tmp_path,
        log_path,
        session_id="codex-test-session",
    )
    assert len(results) == 1
    assert results[0]["verdict"] == "PASS"
    assert results[0]["exit_code"] == 0

    state = json.loads((epic_dir / "state.json").read_text(encoding="utf-8"))
    assert state.get("last_verify_verdict") == "PASS"


def test_mirror_codex_collab_verdicts_verify_qa_fail(tmp_path: Path) -> None:
    _ensure_gate_agents(tmp_path, "verify-qa", "reviewer")
    epic_dir = tmp_path / ".claude" / "runtime" / "epic"
    epic_dir.mkdir(parents=True, exist_ok=True)
    (epic_dir / "state.json").write_text(
        json.dumps(
            {
                "schema_version": "loop-state/v2",
                "active": True,
                "status": "running",
                "session_id": "codex-qa-session",
                "armed_step": "QA",
                "armed_epic": "T-HUB-044",
                "projection": {
                    "epic_id": "T-HUB-044",
                    "role": "BACK",
                    "phase": "QA",
                    "projection_hash": "sha256:test",
                    "phase_epoch": "sha256:test",
                    "event_digest": "sha256:test",
                },
            }
        ),
        encoding="utf-8",
    )
    log_path = tmp_path / "session.log"
    log_path.write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "wait-qa",
                    "type": "collab_tool_call",
                    "tool": "wait",
                    "agents_states": {
                        "thread-qa": {
                            "status": "completed",
                            "message": (
                                "```json\n"
                                '{"schema":"loop-gate-verdict/v1",'
                                '"agent_id":"verify-qa",'
                                '"verdict":"FAIL",'
                                '"step_id":"QA",'
                                '"session_id":"codex-qa-session",'
                                '"epic_id":"T-HUB-044",'
                                '"recorded_at":"2026-09-02T00:00:00Z"}\n'
                                "```"
                            ),
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    results = mirror_codex_collab_verdicts_from_log(
        tmp_path,
        log_path,
        session_id="codex-qa-session",
    )
    assert len(results) == 1
    assert results[0]["agent_type"] == "verify-qa"
    assert results[0]["verdict"] == "FAIL"
    assert results[0]["exit_code"] == 0

    state = json.loads((epic_dir / "state.json").read_text(encoding="utf-8"))
    assert state.get("reviewer_verdict") == "FAIL" or state.get(
        "last_verify_verdict"
    ) == "FAIL"
