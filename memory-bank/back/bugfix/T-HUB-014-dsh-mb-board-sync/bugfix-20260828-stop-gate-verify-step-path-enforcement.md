# BACK BUGFIX — T-HUB-014-dsh-mb-board-sync — stop-gate verify step path enforcement

- **Дата:** 2026-08-28
- **Источник:** `memory-bank/back/qa/T-HUB-014-dsh-mb-board-sync/qa-20260828-dsh-mb-board-sync.yaml`, Fix plan #1
- **Эпик:** `T-HUB-014-dsh-mb-board-sync`
- **Статус:** исправлено; требуется повторный BACK QA

## Симптом

`agent-pretool.py` разрешал запуск `@verify`, когда implement step отсутствовал на диске или не был указан в `ALLOW READ`. Полный backend suite падал в `test_agent_pretool_denies_verify_when_step_missing` и `test_agent_pretool_denies_verify_without_step_in_allow`.

## Root cause

Проверка `verify_step_path_violations()` была условно пропущена веткой `skip_implement_path`, если `need_verify` был выключен, режим не был `implement` или активным шагом был `DECOMPOSE`. Это превращало состояние отсутствующего implement step в разрешение вместо fail-closed deny. Для `@verify` проверка наличия step path и файла должна выполняться независимо от lifecycle-флагов; docs-only DECOMPOSE не должен менять контракт явного запуска `@verify`.

## Изменение

- Удалён `skip_implement_path` и безусловно восстановлен вызов `verify_step_path_violations(cwd, prompt)` для активного `@verify`.
- Сохранены существующие проверки `verify_already_pass`, отсутствующего `activeContext` и исчерпанных retry без `VERDICT`.
- Изменение ограничено `.claude/hooks/agent-pretool.py`; существующие regression tests покрывают оба failing сценария.

## Проверка

- `timeout 300s .venv/bin/pytest -q --tb=line loop/tests/test_stop_gate.py -k 'agent_pretool_denies_verify_when_step_missing or agent_pretool_denies_verify_without_step_in_allow'` — **2 passed**.
- `timeout 300s .venv/bin/pytest -q --tb=line` — **7758 passed, 181 skipped, 48 warnings**.
- `python3 -m py_compile .claude/hooks/agent-pretool.py` — **PASS**.
- `git diff --check -- .claude/hooks/agent-pretool.py` — **PASS**.
- `.venv/bin/graphify update .` — не выполнен: в репозитории отсутствует `.venv/bin/graphify` (exit 127).

## Свежая проверка — 2026-08-29

- Regression-сценарии и связанные board-sync проверки прошли в targeted suite: **53 passed**.
- Изменения hook-логики входят в текущий полный suite evidence из QA rerun: **7758 passed, 181 skipped, 48 warnings**.

## Acceptance

- [x] Missing implement step denies `@verify` with `step_missing`.
- [x] Step absent from `ALLOW READ` denies `@verify` with `step_not_in_allow`.
- [x] Existing full backend suite is green.
- [ ] Board-sync lint cleanup from QA Fix plan #2 — отдельный следующий bugfix step.

## Следующий шаг

`BACK QA T-HUB-014-dsh-mb-board-sync` — повторить QA с full suite evidence; после QA перейти к отдельному Fix plan #2 для board-sync lint cleanup, если lint blocker сохранится.
