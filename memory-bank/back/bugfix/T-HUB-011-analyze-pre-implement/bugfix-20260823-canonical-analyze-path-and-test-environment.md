# BACK BUGFIX — T-HUB-011 canonical ANALYZE path и test environment

- **Дата:** 2026-08-27
- **Источник:** `memory-bank/back/qa/T-HUB-011-analyze-pre-implement/qa-20260827-analyze-pre-implement.yaml`, Fix plan 1
- **Эпик:** `T-HUB-011-analyze-pre-implement`
- **Статус:** исправлено, BACK QA pass (2026-08-27)

## Симптомы

1. В унаследованном окружении hub тесты hook/state получали `deny`, не находили временный `spawn-gate` state и давали ошибки JSON.
2. `validate-step` для временных security/refactor/QA fixtures разрешал путь относительно hub, поэтому фикстуры вне hub сообщали `missing ... yaml`.
3. Полный suite завершался 18 failures в `loop/tests`, несмотря на проход ANALYZE path-contract и spec-kit collection.

## Root cause

`PROJECT_ROOT` и `DEV_HUB` в loop-сессии указывали на hub. Изменённый `product_cwd` безусловно предпочитал `PROJECT_ROOT`, а `state_path` всегда выбирал hub runtime при наличии `DEV_HUB`; это смешивало payload cwd временного теста с состоянием hub. Аналогичная ошибка в `resolve_cli_cwd` перенаправляла default cwd на `PROJECT_ROOT`, даже когда процесс уже работал в изолированном временном каталоге.

## Изменения

- `product_cwd` перенаправляет cwd в `PROJECT_ROOT` только когда текущий cwd действительно является hub.
- `resolve_cli_cwd` применяет default `PROJECT_ROOT` только из hub cwd и сохраняет явный изолированный cwd.
- `state_path` использует локальный `<cwd>/.claude/runtime/spawn-gate`, когда `PROJECT_ROOT` совпадает с hub, но payload cwd изолирован; production product по-прежнему использует hub runtime.
- Сохранена canonical ANALYZE path и установка `spec-kit[test]` из предыдущего fix.

## Проверки

- `timeout 300s .venv/bin/pytest loop/tests/test_agent_hooks.py loop/tests/test_stop_gate.py loop/tests/test_shard_parity.py loop/tests/test_validate_decompose.py -q --tb=line` — `101 passed`.
- Та же targeted-команда в очищенном окружении без `PROJECT_ROOT`, `DEV_HUB`, `HUB_ROOT`, `CLAUDE_PROJECT_DIR`, `PROJECT_WORKFLOW_HOOKS`, `EPIC_LOOP` — `101 passed`.
- `timeout 300s .venv/bin/pytest spec-kit/tests -q --tb=line` — `7318 passed, 181 skipped, 48 warnings`.
- `timeout 300s .venv/bin/pytest -q --tb=line` — `7678 passed, 181 skipped, 48 warnings`.
- `git diff --check -- .claude/hooks/_lib.py` — PASS.

## Out of scope

- Frontend test runners не применялись: frontend в scope отсутствует.
- Изменение `spec-kit/pyproject.toml` не требуется: зависимости уже объявлены.

## Next

`BACK QA T-HUB-011-analyze-pre-implement` повторён 2026-08-27 и завершён с `verdict: pass`; следующий lifecycle шаг — `BACK REFLECT`.
