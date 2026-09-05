# BUGFIX: mb-finish-reflect-cleanup

- **Epic:** `T-HUB-060-remove-reflect-phase`
- **Date:** 2026-09-05
- **Role:** BACK
- **Источник:** `memory-bank/back/qa/T-HUB-060-remove-reflect-phase/qa-20260905-remove-reflect-phase.yaml` §Fix plan (`BACK BUGFIX mb-finish-reflect-cleanup`)
- **Skills:** `systematic-debugging`, `tdd`, `python-testing-patterns`, `python-error-handling`, `verification-before-completion`

## 1. Симптом и QA Findings
- **ISS-001:** `ImportError: cannot import name 'find_reflection_artifact' from 'harness.hooks.epic.core'` при импорте / исполнении `finish_reflect` в `loop/mb_finish/impl.py`.
- **ISS-002:** 4 failing tests в `harness/hooks/tests/`:
  - `test_finish_reflect_happy`
  - `test_finish_reflect_no_artifact`
  - `test_uniform_contract_matrix[finish_reflect]`
  - `test_full_mb_finish_suite_green`

## 2. Root Cause
В эпике `T-HUB-060-remove-reflect-phase` была полностью вырезана фаза `REFLECT` и удалена функция `find_reflection_artifact` из `harness/hooks/epic/core.py`. Однако устаревшие вызовы и дескрипторы `finish_reflect` оставались в:
1. `loop/mb_finish/impl.py` (где функция пыталась импортировать удалённую `find_reflection_artifact`).
2. `loop/mb_finish/mcp_server.py` (инструмент MCP `finish_reflect`).
3. `harness/hooks/epic_resolve.py` (CLI subparser `mb-finish reflect`).
4. `harness/hooks/tests/test_mb_finish_creative.py` и `test_mcp_parity.py` (тесты, вызывающие `finish_reflect`).

## 3. Решение (Fix)
1. Удалена неиспользуемая функция `finish_reflect` из `loop/mb_finish/impl.py`.
2. Удалён `finish_reflect` из экспортов и MCP инструментов в `loop/mb_finish/mcp_server.py`.
3. Удалён CLI subparser и обработчик `mb-finish reflect` из `harness/hooks/epic_resolve.py`.
4. Обновлены тесты `harness/hooks/tests/test_mb_finish_creative.py` и `test_mcp_parity.py` с удалением устаревших проверок вырезанной фазы REFLECT.

## 4. Regression Evidence & Test Verification
- Targeted pytest: `bin/pytest harness/hooks/tests/ -q --tb=line` — PASS
- Full test suite: `bin/pytest -q --tb=line` — 1942 passed, 3 skipped (100% green).
