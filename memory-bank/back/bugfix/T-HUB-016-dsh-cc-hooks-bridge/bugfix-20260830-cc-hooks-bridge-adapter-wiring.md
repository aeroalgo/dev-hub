# BACK BUGFIX — T-HUB-016-dsh-cc-hooks-bridge — cc-hooks-bridge adapter wiring

- **Дата:** 2026-08-30
- **Источник:** `memory-bank/back/qa/T-HUB-016-dsh-cc-hooks-bridge/qa-20260830-cc-hooks-bridge.yaml`, Fix plan B1/B2/B3
- **Эпик:** `T-HUB-016-dsh-cc-hooks-bridge`
- **Статус:** исправление подтверждено targeted regression и полным suite; требуется повторный BACK QA

## Симптом

BACK QA выявил, что `dsh/plugins/mb-bridge/src/index.ts` регистрировал HTTP routes, но не подключал адаптеры Cordis для `task-board.stock-run` и `workspace.list`. Из-за этого live stock-run не передавал mb-карточки в loop bridge, а host workspace list не был доступен board UI через согласованный slot.

## Root cause

Entrypoint оставался на старом контракте: он инжектировал UI placeholders, но не использовал созданные host adapters. При переходе на `Context`/`webServer` routes импортированные `createStockRunAdapter` и `createWorkspaceListAdapter` отсутствовали в `apply()`, поэтому их producer/consumer wiring не доходил до Cordis runtime. Профиль `epic-bugfix` также содержал bridge fragment и package dependency без синхронизированного lockfile.

## Исправление

- `dsh/plugins/mb-bridge/src/index.ts` теперь инжектирует `createStockRunAdapter(config)` через `ctx.inject?.(STOCK_RUN_SLOT, ...)`.
- Тот же entrypoint инжектирует `createWorkspaceListAdapter(bridgeContext)` через `ctx.inject?.('workspace.list', ...)`.
- Сохранены web-server routes и non-mb stock-run delegation из `intercept-run.ts`; explicit unavailable/invalid states workspace adapter не изменялись.
- `dsh/profiles/epic-bugfix/cordis.patch.yml` монтирует shared `cc-hooks-bridge.yml`, а `package.json` и `pnpm-lock.yaml` фиксируют `@deepseek-ai/dsh-hooks-claude-code@0.0.1-rc.5`.
- Regression coverage закрепляет bridge fragment, configPath/projectDir и наличие bridge во всех epic-профилях.

## Проверка исправления

- `timeout 300s .venv/bin/pytest loop/tests/test_board_launch_bridge_unit.py loop/tests/test_board_launch_ui_filter.py tests/test_cc_hooks_bridge_config.py -q --tb=line` — `24 passed`.
- `timeout 300s .venv/bin/pytest -q --tb=line` — `7863 passed, 181 skipped, 48 warnings`.
- `git diff --check -- dsh/profiles/epic-bugfix/cordis.patch.yml dsh/profiles/epic-bugfix/package.json dsh/profiles/epic-bugfix/pnpm-lock.yaml dsh/plugins/mb-bridge/src/index.ts tests/test_cc_hooks_bridge_config.py` — PASS.
- `pnpm install --lockfile-only --ignore-scripts` в `dsh/profiles/epic-bugfix` — PASS; lockfile содержит hook package и его peer graph.

## Integration check (§0.11)

- `cc-hooks-bridge` → `@deepseek-ai/cordis-plugin-include` → `dsh/patches/cc-hooks-bridge.yml` → `@deepseek-ai/dsh-hooks-claude-code`.
- Shared fragment передаёт `configPath` и `projectDir` из `CLAUDE_PROJECT_DIR`; профиль dependency и lockfile обеспечивают установленный hook package.
- `task-board.stock-run` consumer получает adapter из entrypoint; non-mb карточки сохраняют исходный `stockRun` handler.
- `workspace.list` consumer получает host adapter с явными состояниями `ready`, `unavailable`, `invalid`.

## Acceptance

- [x] B1: stock-run adapter зарегистрирован на `task-board.stock-run`.
- [x] B2: workspace-list adapter зарегистрирован на `workspace.list`.
- [x] B3: bridge profile dependency/config wiring синхронизированы и проверены targeted tests.
- [ ] Повторный BACK QA с полным suite и reviewer gate.

## Следующий шаг

`BACK QA T-HUB-016-dsh-cc-hooks-bridge` — повторить эпический QA после adapter wiring. До QA pass переход к REFLECT запрещён.
