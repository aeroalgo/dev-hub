# Bugfix: Codex gate step_id ownership NEED_HUMAN

**Epic:** T-HUB-080-workflow-capability-instruction-parity  
**Author:** BACK BUGFIX  
**Date:** 2026-09-10

## Симптом
`verify-bugfix` под Codex писал в fence `step_id: "s05"` (контекст эпика), ownership gate ожидал `BUGFIX` → `NEED_HUMAN: semantic_ownership_mismatch (step_id mismatch…)`, сессия останавливалась несмотря на валидный semantic FAIL verdict.

## Root cause
1. Codex native `multi_agent` не инжектит `GATE_IDENTITY` в child до старта (SubagentStart в lifecycle вызывается post-wait).
2. Coerce на `SubagentStop` покрывал только `session_id`, не `step_id` / `epic_id`.
3. Шаблон `verify-bugfix` требовал плейсхолдер `<step_id>`, LLM подставлял implement-step (`sNN`).

## Fix
- `harness/hooks/subagent-stop.py`: для `runtime_id=codex` transport-binding coerce `session_id` + `step_id` + `epic_id` из in-flight identity (Claude остаётся strict).
- `harness/agents/verify-bugfix.md`: литерал `step_id: "BUGFIX"`.
- `harness/agents/verify-qa.md`: литерал `step_id: "QA"`.
- Regression: `loop/tests/test_codex_session_ownership_coerce.py`.

## AC+
1. Codex fence с чужим `step_id`/`epic_id` не даёт `semantic_ownership_mismatch`.
2. Claude fence с чужим `step_id` по-прежнему FAIL ownership (T-HUB-066).
3. Agent source для verify-bugfix фиксирует `BUGFIX`.

## AC−
1. Нет ослабления Claude ownership.
2. Нет schema-retry вместо ownership на Claude stale step.

## Verify
`bin/pytest loop/tests/test_codex_session_ownership_coerce.py loop/tests/test_stop_gate.py::test_stale_step_id_semantic_ownership_mismatch loop/tests/test_stop_gate.py::test_ownership_mismatch_no_schema_retry -v`
