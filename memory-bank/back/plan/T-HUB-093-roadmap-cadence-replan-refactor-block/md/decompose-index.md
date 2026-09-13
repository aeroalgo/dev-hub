# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-093-roadmap-cadence-replan-refactor-block
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-12
**Режим:** BACK DECOMPOSE

Нарезка реализует блок исполнения ритма дорожной карты (roadmap cadence replan/refactor block): проведение фазы `replan` для пары завершённых фич (`pair_ids`) с обязательной фиксацией решения (`complete` или `skip` со структурированным evidence), последующий переход в фазу `refactor` (вставка эпика с `kind: refactor` в начало очереди либо noop evidence), перевод в фазу `resync` после завершения refactor без увеличения счётчика фич, связывание `roadmap_advance` и `context_loop` для армирования команд `BACK REPLAN` и `BACK PLAN REFACTOR`, обновление правил workflow (запрет переноса шагов anti-carry и скользящих окон) и финальный sunset purge. Всего 6 sNN (целевой диапазон 5–8).

## Requirements coverage

| Req ID | Plan FR text | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `advance_replan` / record skip\|complete per pair id | s01, s06 | Типизированная модель `ReplanEvidence`/`ReplanSkipRecord` и метод `advance_replan` в `loop/roadmap_cadence.py`. |
| FR-002 | transition to refactor only when pair done | s01, s02, s06 | Перевод `cadence.phase` в `refactor` строго после закрытия всех `pair_ids`. |
| FR-003 | `start_refactor_phase` upsert+arm or noop | s02, s06 | Функции `start_refactor_phase` и `record_refactor_noop` в `loop/roadmap_cadence.py` и `loop/roadmap_queue.py`. |
| FR-004 | mark refactor epic done → handoff phase for 094 (resync) | s02, s03, s06 | Метод `on_refactor_done` переводит фазу в `resync` без инкремента feature counter (resync логика в follow_up: T-HUB-094-roadmap-cadence-resync-tail). |
| FR-005 | Wire roadmap_advance to arm REPLAN/PLAN REFACTOR commands via activeContext identity | s03, s06 | Автоматическое армирование `BACK REPLAN <pair_id>` и `BACK PLAN REFACTOR <epic_id>` в `loop/context_loop.py` и `loop/roadmap_queue.py`. |
| FR-006 | Tests order + skip evidence | s01, s02, s03, s05, s06 | Юнит- и сквозные тесты в `loop/tests/test_roadmap_cadence.py` и `loop/tests/test_roadmap_queue.py`. |
| FR-007 | Kind I workflows replan + plan-refactor | s04, s06 | Обновление `workflow-replan.mdc`, `workflow-plan-refactor.mdc` и `mainrule.mdc` с фиксацией порядка и anti-carry policy. |
| REQ-CRITICAL-ONLY | Gap-фильтр учитывает только критические gaps; косметические gaps не создают work | s01, s02, s03, s05, s06 | Только critical gaps могут запускать cadence work; cosmetic gaps завершаются без создания работы. |
| US-001 | REPLAN arms/skips pair ids | s01, s03, s06 | Последовательное прохождение pair_ids до терминального состояния. |
| US-002 | refactor blocked early | s01, s02, s06 | Блокировка вызова refactor API до закрытия replan (fail-closed). |
| US-003 | refactor epic or noop | s02, s03, s06 | Вставка эпика с `kind: refactor` XOR фиксация noop evidence. |
| US-004 | no neighbor carry steps | s04, s06 | Строгий запрет на перенос незакрытых шагов в соседние эпики (anti-carry policy). |
| TM-01 | refactor before replan done → fail | s02, s05, s06 | Запрет запуска refactor при активной фазе replan. |
| TM-02 | both skipped → noop refactor allowed | s02, s05, s06 | Возможность пропуска refactor при отсутствии gap/refactor задач. |
| TM-03 | refactor kind not counted as feature | s02, s03, s05, s06 | Завершение refactor не увеличивает счётчик feature counter (инвариант 092). |
| TM-04 | rules forbid window/carry | s04, s05, s06 | Правила запрещают скользящие окна и перенос шагов в соседа. |
| AC+ | cannot arm refactor in replan; after pair skip/complete → refactor or noop; tests enforce order; rules state REPLAN→Refactor | s01, s02, s03, s04, s05, s06 | Соблюдение строгого порядка фаз cadence-блока и валидация тестами. |
| AC− | no refactor-before-replan path; no replan-of-replan; no carry FR steps; no implementing from-queue resync here | s01, s02, s03, s04, s05, s06 | Отсутствие обходных путей, запрет replan-of-replan; resync в follow_up: T-HUB-094-roadmap-cadence-resync-tail. |
| Out of scope | Reconcile from-queue + resync tail | — | follow_up: T-HUB-094-roadmap-cadence-resync-tail |

## Stages coverage

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| 1. Gap evidence model + skip/complete API | plan.md §Technology axiom & FR-001 | s01 |
| 2. Refactor phase state machine + queue upsert / noop API | plan.md §Target layout & FR-002, FR-003, FR-004 | s02 |
| 3. Arm REPLAN and PLAN REFACTOR command wire | plan.md §Target layout & FR-005, US-001, US-003 | s03 |
| 4. Kind I workflows replan + plan-refactor & anti-carry policy | plan.md §Target layout & FR-007, US-004, TM-04 | s04 |
| 5. CLI extension & block e2e progression tests | plan.md §QA consumes draft & FR-006, TM-01..TM-03 | s05 |
| 6. legacy-fallback-purge (A+B+C+I) | plan.md §Replacement / sunset & transition gate | s06 |

## Outcome map

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Типизированный сбор доказательств gap-анализа и последовательное закрытие pair_ids (US-001, FR-001) | s01, s06 |
| Строгая блокировка входа в refactor до завершения всех pair_ids (US-002, TM-01, FR-002) | s01, s02, s06 |
| Добавление refactor-эпика с `kind: refactor` в очередь либо фиксация noop evidence (US-003, TM-02, FR-003) | s02, s06 |
| Корректный переход в phase `resync` после закрытия refactor без ложного роста feature counter (FR-004, TM-03) | s02, s03, s06 |
| Автоматическое армирование `BACK REPLAN` и `BACK PLAN REFACTOR` в activeContext (FR-005) | s03, s06 |
| Инструкции workflow с явным запретом переноса шагов в соседа и скользящих окон (US-004, TM-04, FR-007) | s04, s06 |
| Сквозные тесты полного цикла исполнения cadence-блока и расширенная CLI-диагностика (FR-006) | s05, s06 |
| Только critical gaps создают cadence work; cosmetic gaps не создают работу (REQ-CRITICAL-ONLY) | s01, s02, s03, s05, s06 |
| Полное устранение устаревших путей запуска refactor и ручного replan вне cadence (A+B+C+I) | s06 |
| Out of scope: синхронизация очереди и хвост resync | follow_up: T-HUB-094-roadmap-cadence-resync-tail |

## Replacement cleanup

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Ручной REPLAN без координации с cadence-фазами | A | Интеграция REPLAN в фазы cadence SoT (`replan`) | s01, s03, s06 | no | Исполнение REPLAN строго по `pair_ids`. |
| Запуск refactor в любое время в обход replan | B | Fail-closed гейт, требующий закрытия всех `pair_ids` | s01, s02, s06 | no | Блокировка входа в refactor до конца replan. |
| Необязательный refactor / тихий пропуск без evidence | C | Структурированный `record_refactor_noop` с фиксацией evidence | s02, s06 | no | Запрет тихого пропуска без записи. |
| Допущение о переносе незакрытых шагов в соседа / скользящих окнах | I | Строгая anti-carry policy и правило one-hop per ID | s04, s06 | no | Обновление `workflow-replan.mdc` и `workflow-plan-refactor.mdc`. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-replan-gap-evidence-and-advance-api.yaml](../yaml/steps/s01-replan-gap-evidence-and-advance-api.yaml) | [s01-replan-gap-evidence-and-advance-api.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s01-replan-gap-evidence-and-advance-api.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-refactor-phase-api-and-queue-upsert.yaml](../yaml/steps/s02-refactor-phase-api-and-queue-upsert.yaml) | [s02-refactor-phase-api-and-queue-upsert.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s02-refactor-phase-api-and-queue-upsert.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-arm-replan-and-plan-refactor-command-wire.yaml](../yaml/steps/s03-arm-replan-and-plan-refactor-command-wire.yaml) | [s03-arm-replan-and-plan-refactor-command-wire.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s03-arm-replan-and-plan-refactor-command-wire.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-workflow-rules-and-anti-carry-policy.yaml](../yaml/steps/s04-workflow-rules-and-anti-carry-policy.yaml) | [s04-workflow-rules-and-anti-carry-policy.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s04-workflow-rules-and-anti-carry-policy.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cadence-status-cli-and-block-e2e-tests.yaml](../yaml/steps/s05-cadence-status-cli-and-block-e2e-tests.yaml) | [s05-cadence-status-cli-and-block-e2e-tests.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s05-cadence-status-cli-and-block-e2e-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06-legacy-fallback-purge.yaml](../../implement/T-HUB-093-roadmap-cadence-replan-refactor-block/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**Следующий режим после завершения дерева:** BACK ANALYZE. `ANALYZE deferred` не используется.
