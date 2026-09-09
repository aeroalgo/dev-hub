from __future__ import annotations

from loop.runtime_adapters.agent_contract import get_agent_contract_adapter


_VALID_VERDICT = (
    "```json\n"
    "{\n"
    '  "schema": "loop-gate-verdict/v1",\n'
    '  "agent_id": "verify-qa",\n'
    '  "verdict": "PASS",\n'
    '  "step_id": "QA",\n'
    '  "session_id": "session-1",\n'
    '  "epic_id": "T-HUB-084",\n'
    '  "recorded_at": "2026-09-09T12:00:00Z"\n'
    "}\n```")


def test_claude_codex_and_dsh_use_one_contract_text() -> None:
    adapters = [
        get_agent_contract_adapter("claude"),
        get_agent_contract_adapter("codex"),
        get_agent_contract_adapter("dsh"),
    ]

    assert len({adapter.contract("verify-qa") for adapter in adapters}) == 1
    assert len({adapter.contract_hash("verify-qa") for adapter in adapters}) == 1


def test_runtime_adapters_parse_the_same_gate_verdict() -> None:
    for runtime_id in ("claude", "codex", "dsh"):
        record = get_agent_contract_adapter(runtime_id).parse_gate_verdict(_VALID_VERDICT)
        assert record is not None
        assert record.agent_id == "verify-qa"
        assert record.verdict == "PASS"


def test_universal_contract_rejects_incomplete_verdict() -> None:
    adapter = get_agent_contract_adapter("codex")
    incomplete = _VALID_VERDICT.replace('  "session_id": "session-1",\n', "")

    assert adapter.parse_gate_verdict(incomplete) is None
