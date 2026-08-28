---
schema: epic-reflect/v1
epic_id: T-HUB-006-dsh-loop-runtime-adapter
task_id: T-HUB-006-dsh-loop-runtime-adapter
date: "2026-08-27"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-006-dsh-loop-runtime-adapter

## Итог

Эпик добавил opt-in DSH runtime adapter к loop без изменения Claude default path. Реализованы валидация `EPIC_RUNTIME`, чистый `loop/runtime_adapters/dsh.py`, runtime-поля в `prepare_session`, dispatch в `loop.sh`, DSH-классификация в `session_resilience.py`, scaffold `dsh/` и fake-DSH regression coverage. Дополнительные audit remediation шаги s08–s09 закрыли argv-совместимость resolver-а и fail-closed detection подмены модели.

Все s01–s09 имеют `status: completed` в decompose index. BACK QA завершён с `verdict: pass`, `issues: []`, `blockers: []` и пустым `fix_plan`; после исправления регрессии полный `loop/tests/` прошёл: 541 тест. Эта REFLECT-сессия не меняла продуктовый код: `code_changed: no`.

Ограничения остаются явными: настоящий внешний DSH API/network не запускался, использовались fake DSH и fixture-сценарии; `.venv/bin/graphify` отсутствует в checkout и graph update не выполнялся. Frontend-поверхности у эпика нет.

## vs plan / decompose

| Требование / outcome | Покрытие | Статус |
|---|---|---|
| FR-1: `EPIC_RUNTIME` только `claude|dsh`, invalid config fail-closed | s01, runtime-config tests | ✅ |
| FR-2: `--runtime claude|dsh` переопределяет env | s03, prepare CLI tests | ✅ |
| FR-3: `run_agent_session()` dispatches Claude или DSH | s04, dispatch tests | ✅ |
| FR-4: DSH command/profile/prompt и session log | s04, s08, fake-DSH integration | ✅ |
| FR-5: `prepare` эмитирует `runtime`, `dsh_profile`, `dsh_workspace` | s03, context-loop tests | ✅ |
| FR-6: pure `build_command()` и `normalize_log_for_analysis()` | s02, adapter tests | ✅ |
| FR-7: completed/transient/permanent DSH analysis | s05, fixtures and resilience tests | ✅ |
| FR-8: exit 0 без FINISH классифицируется как abort | s05, e2e/analysis tests | ✅ |
| FR-9: README, resolver и profile landing pads | s06, shell/content checks | ✅ |
| FR-10: unit/integration/regression suite | s01, s02, s05, s07–s09 | ✅ |
| NFR-1: unset runtime сохраняет Claude path | s07, full loop suite | ✅ |
| NFR-2: общий `session_resilience.py` wrapper сохраняется | s04–s05, QA counterpart check | ✅ |
| NFR-3: DSH model substitution — отдельный non-retryable HALT | s09, mismatch tests | ✅ |
| NFR-4: TDD pure functions до shell wiring | s01, s02, s05 | ✅ |
| NFR-5: flock/roadmap/DAG/prepare halt matrix не изменены по scope | все shards, QA §0.11 | ✅ |
| AC+1…AC+6 и AC−1…AC−5 | s01–s09, QA | ✅ |
| Plan phases s01–s07 и audit additions s08–s09 | decompose index + implement shards | ✅ |
| Replacement cleanup | greenfield extension; `deletes: []` по shards | ✅ |

Плановая граница соблюдена: DSH добавлен как opt-in ветка, Claude runner не удалён, silent DSH→Claude fallback запрещён. QA первоначально выявил lifecycle regression и scope leakage; они были исправлены отдельным BUGFIX до итогового PASS, а unrelated stale-arm API/test удалены из diff этого эпика.

## Successes

- Runtime contract начинается с безопасного default: unset `EPIC_RUNTIME` выбирает Claude, unsupported value завершается диагностируемой ошибкой.
- Adapter оставлен pure-function слоем; state/lifecycle logic не продублированы в DSH-модуле.
- Dispatch и resolver покрывают explicit executable path, global command и bounded `npx` argv, сохраняя аргументы раздельно и не используя fallback на Claude.
- DSH log normalization и classification дают parity для completed, transient, permanent и incomplete FINISH сценариев.
- Model mismatch проверяется до transient/permanent классификации и переводится в `model_substitution`, `retryable=false`, `backoff_sec=0`.
- Scaffold `dsh/` оставляет T-HUB-007 landing pad без подключения профилей или Cordis plugins вне scope.
- Regression evidence усилилась от targeted checks до полного suite: 34 targeted tests и 541 tests в `loop/tests/` прошли; `bash -n loop/loop.sh` также PASS.
- QA и reviewer подтвердили AC+/AC−/§0.11; финальный QA artifact не содержит issues, blockers или fix-plan rows.
- После QA failure scope был возвращён к owning epic: несвязанный stale-arm surface удалён, а checkpoint `next_step` transition восстановлен без ослабления fail-closed для `same_step`.

## Problems

- QA timeline содержит три `qa_fail` (seq 2, 4, 5) и два `bugfix_done` (seq 3, 6) до `qa_pass` (seq 7). Проблемы были устранены с продвижением, но эпик потребовал повторных QA/BUGFIX циклов.
- Первый diff смешивал DSH lifecycle changes с checkpoint resume regression и stale-arm API/test другого направления. Это вызвало красный full suite и scope leakage.
- `events.jsonl` содержит `audit_done`, QA и BUGFIX events, но не содержит `implement_done` для s01–s09. Статусы и evidence есть в implement shards/index, однако event timeline не является полной историей финализации.
- Runtime snapshot зафиксировал `retry_count: 5`, `state_rebuilt: true`, `degraded_count: 2`, широкий `dirty` список с артефактами других T-HUB и активный `REFLECT` checkpoint. Это ограничивает чистоту атрибуции, хотя итоговый QA scope и event sequence не показывают бесконечного same-step loop или role drift.
- `last-session.json` указывает на завершённый BUGFIX с `outcome: clean`, но не на отдельный завершённый REFLECT; `state.json` на момент снимка ещё имел `status: running`. Это runtime-наблюдаемость, а не незакрытое требование эпика.
- Graphify CLI недоступен, поэтому требуемый graph update нельзя было выполнить; внешний DSH network path также не был проверен.

## Lessons

1. Adapter boundary нужно проверять не только по строке команды, но и по argv-модели: bare resolver commands и explicit paths имеют разные правила executable validation.
2. Для opt-in runtime fail-closed важнее silent compatibility: отсутствующий DSH, invalid config и model substitution должны давать отдельные диагностируемые non-success outcomes без Claude fallback.
3. Targeted TDD до shell wiring сокращает поверхность отладки; после shell changes обязательный full regression нужен для lifecycle-контрактов, не только для DSH tests.
4. Scope isolation должна быть частью реализации, а не только QA: изменения checkpoint/stale-arm нельзя смешивать с DSH epic без owning-epic ownership check.
5. Machine index и implement shards обеспечивают трассируемость, но без `implement_done` event-ов orchestration timeline остаётся неполной.
6. Runtime state и test fixtures должны использовать изолированные project paths; ambient `PROJECT_ROOT` способен маскировать или создавать ошибки, не относящиеся к текущему shard.

## Improvements

- Добавить emission `implement_done` в `finalize-step` для каждого shard либо одного batch event с перечнем sNN, чтобы `events.jsonl` отражал фактический путь реализации.
- Встроить перед QA source/scope audit: список changed files должен сверяться с owning epic, а unrelated API/test должен блокировать продвижение до явного удаления или переноса.
- Усилить loop convergence diagnostics: различать retry, который продвинулся через BUGFIX/QA, и retry без изменения fingerprint; выдавать короткий reason вместо широкого dirty snapshot.
- Изолировать test runtime через явное снятие `PROJECT_ROOT` и временные state roots во всех lifecycle fixtures; добавить assertion, что canonical `.claude/runtime/epic/*` не загрязняется временными путями.
- Добавить preflight/CI проверку доступности `.venv/bin/graphify` или явный диагностический режим для среды, где graphify отсутствует, чтобы обязательный post-code-change шаг не терялся молча.
- Сохранить bounded session-log diagnostics и retention для abort/halt/FINISH/retry markers; REFLECT должен читать только такой срез, а не полный log dump.

## Orchestration signals

| Источник | Наблюдение | Интерпретация |
|---|---|---|
| `memory-bank/back/events/T-HUB-006-dsh-loop-runtime-adapter/events.jsonl` | seq1 `audit_done`; seq2/4/5 `qa_fail`; seq3/6 `bugfix_done`; seq7 `qa_pass` | QA failures были исправлены и завершились PASS; timeline показывает advance, не бесконечный retry |
| `.claude/runtime/epic/last-session.json` | `status: completed`, `outcome: clean`, `resume_from: BUGFIX`, `retry_count: 5`, `abort_kind: null` | Сессия завершила BUGFIX clean, но счётчик retries и broad dirty snapshot требуют более чистой диагностики |
| `.claude/runtime/epic/checkpoint.json` | checkpoint `REFLECT`, `stage: prepared`, `resume_policy: same_step`, `retry_count: 0` | Текущий REFLECT вызов подготовлен; same-step policy не свидетельствует о runtime loop сама по себе |
| `.claude/runtime/epic/state.json` | `phase: REFLECT`, `state_rebuilt: true`, `context_degraded: true`, `degraded_count: 2`, diagnostic `state_rebuilt` | Контекст был восстановлен после degradation; это сигнал наблюдаемости, не product failure |
| Runtime dirty snapshot | перечислены файлы нескольких T-HUB и общие рабочие изменения | Нужен scope/ownership guard; по snapshot нельзя приписывать все dirty файлы T-HUB-006 |
| `session-4-t5.log` bounded search | доступен log path; поиск abort/halt/FINISH/same-step не дал actionable lifecycle marker | Полный log в reflection не переносился; подтверждение аномалий ограничено |
| decompose index + QA artifact | s01–s09 completed, QA pass, issues/blockers/fix_plan пусты | Реализационная очередь исчерпана, epic completion подтверждён |
| Role/phase sequence | BACK IMPLEMENT → BACK QA/BUGFIX → BACK QA → BACK REFLECT | Role drift и пропуск обязательного QA не обнаружены |
| Graphify | `.venv/bin/graphify` exit 127 | Средовое ограничение, не дефект DSH contract; требует preflight visibility |

## Promote candidates

| Сигнал | → | Решение |
|---|---|---|
| Отсутствуют `implement_done` events | → loop/hooks | Добавить emission в `finalize-step`; текущую историю задним числом не переписывать |
| QA failure из-за смешанного lifecycle и stale-arm diff | → workflow | Добавить ownership/scope gate до QA и явный маршрут переноса unrelated changes |
| `retry_count: 5` при финальном clean outcome | → loop/hooks | Развести progress retry и fingerprint-stall retry в runtime diagnostics |
| `state_rebuilt` + `context_degraded: true` | → loop/hooks | Улучшить snapshot reason/degraded reporting; текущий PASS не переоткрывать |
| Широкий dirty snapshot чужих эпиков | → workflow | Требовать changed-file ownership summary для multi-epic hub work |
| Недоступный graphify binary | → workflow | Добавить preflight check и видимый environment limitation; не подменять graph update другим инструментом |
| Реальный DSH API/network не запускался | → skip | Это ограничение scope/fixture QA, покрытие fake DSH достаточно для текущего epic gate |
| Нет frontend surface | → skip | Frontend tests к этому BACK эпiku не применяются |

## Метрики

- Шагов: 9 / 9 completed (100%).
- QA: `verdict: pass`; issues 0; blockers 0; fix_plan 0.
- Regression: 34 targeted tests; 541 tests в `loop/tests/`; `bash -n loop/loop.sh` — PASS.
- Event-log: 7 событий; 3 `qa_fail`, 2 `bugfix_done`, 1 `qa_pass`, 1 `audit_done`.
- Runtime: `retry_count: 5` в last-session snapshot; current REFLECT checkpoint `retry_count: 0`; `degraded_count: 2`.
- code_changed этой REFLECT-сессии: no.

## Next

- Эпик завершён; после handoff фиксируется отдельная строка `EPIC_DONE`.
- Ручная архивация артефактов допускается только вне текущего loop после его остановки.
- Отложено: event emission, scope/ownership gate, runtime diagnostics, test-path isolation и graphify preflight; они не блокируют текущий PASS.
