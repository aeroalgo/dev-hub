# BUGFIX — T-HUB-085 hook dispatcher suite align

**Дата:** 2026-09-11  
**Эпик:** T-HUB-085-hook-event-dispatcher-consolidation  
**Источник:** `qa-20260911-hook-event-dispatcher-consolidation.yaml` §fix plan / blockers  
**Вердикт:** fixed (targeted regression green)

## Симптом

После cutover на `pretool-dispatch.py` / `posttool-dispatch.py` suite падал: allow-тесты ждали legacy `{}`, materializer писал ключи `pretool-dispatch` вместо `PreToolUse`, тесты звали удалённые entrypoints.

## Root cause

1. **Obsolete allow contract:** старый `bash-pretool` на allow делал `emit({})` / пустой stdout; canonical dispatcher всегда `to_hook_output(PreToolUse)` → `permissionDecision: allow`.
2. **Materializer lag:** `EVENT_MAPPING` / `matcher_for_hook` не знали `pretool-dispatch` / `posttool-dispatch` → Codex hooks.json с неверными event keys; committed `.codex/hooks.json` drift.
3. **Legacy path refs:** loop-тесты ссылались на purged `agent-pretool.py` / `bash-pretool.py` / `write-pretool.py` / `agent-posttool.py`.
4. **Сопутствующие regression после gate SoT:** `_ARM_EPIC_KWARGS` отбрасывал `dsh_preset`; stop-gate сравнивал phase с `"IMPLEMENT"` без normalize (`BACK IMPLEMENT`); PASS без receipt → `receipt_missing` раньше ожидаемых diagnostics.

## Fix

- Assert allow через `hookSpecificOutput.permissionDecision == allow`.
- `hooks_json.py` + `parity.py`: map dispatchers → PreToolUse/PostToolUse, matcher `.*`, posttool `timeout_ms=45000`; regenerate `.codex/hooks.json`.
- Retarget loop/tests на canonical dispatchers; TM-001 — in-process deny при hidden agent file.
- `_ARM_EPIC_KWARGS` включает `dsh_preset`; `arm_epic` принимает kwarg.
- stop-gate: `normalize_registry_phase` для IMPLEMENT finish_tool check.
- Тесты stop/handoff: seed `GateIdentity.expected` + `issue_verifier_receipt`.

## Verification

```text
bin/pytest loop/tests/test_stop_gate.py -k 'bash_pretool or verify_already_pass or decompose_uses or mark_index or pass_without_last_finish'
bin/pytest loop/tests/test_codex_hooks_parity_matrix.py loop/tests/test_codex_hooks_bridge.py loop/tests/test_runtime_sync_check.py
bin/pytest loop/tests/test_handoff_strict_flag.py loop/tests/test_phase_verify_gates.py::test_tm001_agent_file_missing_deny
bin/pytest harness/hooks/tests/test_hook_registration_consolidation.py
```

Targeted QA-blocker set: 70 passed / 1 fixed follow-up (`test_verify_already_pass_no_reblock`).

## Next

`@verify-bugfix` → BACK QA full suite → EPIC_DONE только после QA pass.
