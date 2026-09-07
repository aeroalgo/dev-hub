# BUGFIX: Kind I runtime entrypoint phrasing sync

- **Date:** 2026-09-06
- **Epic:** T-HUB-072-context-bundle-fail-closed
- **Source:** QA Fix Plan (`memory-bank/back/qa/T-HUB-072-context-bundle-fail-closed/qa-20260906-context-bundle-fail-closed.yaml`)

## Root Cause
Файлы `.cursor/rules/mainrule.mdc`, `.claude/skills/role-command/SKILL.md` и `harness/claude/skills/role-command/SKILL.md` содержали общую фразу `Read runtime entrypoint`, тогда как тесты `loop/tests/test_kind_i_runtime_entrypoint.py` валидируют строгое наличие фразы `entrypoint текущего runtime`.

## Fix
Синхронизированы формулировки в:
1. `.cursor/rules/mainrule.mdc`
2. `.claude/skills/role-command/SKILL.md`
3. `harness/claude/skills/role-command/SKILL.md`
4. `harness/skills/role-command/SKILL.md`

## Verification
- Unit: `bin/pytest loop/tests/test_kind_i_runtime_entrypoint.py -q --tb=line` (3 passed)
- Full suite: `bin/pytest -q --tb=line` (2170 passed, 3 skipped, 80 warnings)
