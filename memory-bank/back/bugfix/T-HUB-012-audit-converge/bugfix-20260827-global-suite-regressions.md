# BACK BUGFIX — T-HUB-012-audit-converge — global-suite-regressions

- **Дата:** 2026-08-27
- **Источник:** `memory-bank/back/qa/T-HUB-012-audit-converge/qa-20260824-audit-converge.yaml`, Fix plan #1
- **Эпик:** `T-HUB-012-audit-converge`
- **Статус:** исправление подтверждено свежим suite rerun; требуется повторный BACK QA

## Симптом

QA от 2026-08-24 зафиксировал blocker `suite-not-green`: полный backend suite завершился с `110 failed, 7565 passed, 181 skipped`. Падения были сосредоточены в loop runtime/state/stop-gate/roadmap/shard-parity tests и не указывали на нарушение audit-converge AC+/AC−/§0.11.

## Root cause

Blocker был cross-cutting регрессией runtime lifecycle, а не дефектом s01–s04:

1. Унаследованные `PROJECT_ROOT`/`DEV_HUB` могли смешивать hub cwd с изолированным test/product cwd; hook state, CLI paths и fixture resolution выбирали неправильный root.
2. Checkpoint resume дополнительно блокировал допустимый переход `resume_policy=next_step` при ожидаемом несовпадении `step`.
3. В DSH diff находились stale-arm API/test, не относящиеся к owning scope, что загрязняло lifecycle suite.

Эти причины устранены в ранее выполненных scoped bugfix-изменениях T-HUB-011 и T-HUB-006; новый кодовый патч для T-HUB-012 не требуется.

## Проверка исправления

- `env -u PROJECT_ROOT -u DEV_HUB -u HUB_ROOT -u CLAUDE_PROJECT_DIR -u EPIC_LOOP -u PROJECT_WORKFLOW_HOOKS timeout 300s .venv/bin/pytest -q --tb=line` — `7678 passed, 181 skipped, 48 warnings`.
- `timeout 300s .venv/bin/python -m py_compile .claude/hooks/_lib.py .claude/hooks/epic/core.py .claude/hooks/epic_paths.py .claude/hooks/session_resilience.py loop/context_loop.py` — PASS.
- `timeout 300s bash -n loop/loop.sh` — PASS.
- Audit-converge surfaces s01–s04 остаются без изменений; предыдущая проверка QA подтвердила AC+/AC−/§0.11.

## Delta

- **Изменённые product/code-файлы в этом BUGFIX:** нет; исправляющие runtime-изменения уже зафиксированы в scoped артефактах T-HUB-011 и T-HUB-006.
- **Добавлен артефакт:** `memory-bank/back/bugfix/T-HUB-012-audit-converge/bugfix-20260827-global-suite-regressions.md`.
- **Не изменено:** исторический QA artifact от 2026-08-24; его `fail` сохраняется как evidence исходного blocker.

## Acceptance

- [x] Свежий полный backend suite зелёный.
- [x] Hub/product cwd contamination больше не воспроизводится в очищенном окружении.
- [x] Допустимый `resume_policy=next_step` покрыт свежим lifecycle suite.
- [x] Stale-arm scope leakage удалён из DSH changeset.
- [x] Audit-converge AC+/AC−/§0.11 не регрессировали.

## Следующий шаг

`BACK QA T-HUB-012-audit-converge` — повторить эпический QA с тем же scope s01–s04 и свежим suite evidence. До QA pass переход к REFLECT запрещён.
