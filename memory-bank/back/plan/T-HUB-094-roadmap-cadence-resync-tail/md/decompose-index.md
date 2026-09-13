# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-094-roadmap-cadence-resync-tail
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-12
**Режим:** BACK DECOMPOSE

Нарезка реализует завершающий хвост ритма дорожной карты (roadmap cadence resync tail): вызов reconcile для всех эпиков очереди `queue.yaml` через CLI/API `--from-queue`, структурированную фиксацию `ResyncEvidence` на SoT `cadence.yaml`, хелпер инвалидации планов HOW без мутации prompt §Epic, fail-closed resume gate в `roadmap_advance` (блокировка при наличии HIGH drift без evidence), API сброса фазы в `idle` и обнуления счетчика фич (`on_resync_done` / `reset_cadence_idle`), обновление правил и документации Kind I (запрет sliding window) и финальный sunset purge с комплексным E2E тестом. Всего 6 sNN (целевой диапазон 5–8).

## Requirements coverage

| Req ID | Plan FR text | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | reconcile from-queue implementation | s01, s06 | Реализация `reconcile_queue_epics` и опции `--from-queue` в CLI `reconcile-spec`. |
| FR-002 | cadence resync phase + evidence fields | s02, s06 | Модель `ResyncEvidence` и метод `record_resync_evidence` в `loop/roadmap_cadence.py`. |
| FR-003 | resume gate in advance | s03, s06 | Проверка в `roadmap_advance` и `context_loop`: блокировка при `high_count > 0` без evidence. |
| FR-004 | reset API | s04, s06 | API `on_resync_done` / `reset_cadence_idle`: сброс в `idle` и обнуление счетчика. |
| FR-005 | tests | s01, s02, s03, s04, s06 | Набор unit и integration тестов в `test_reconcile_spec.py` и `test_roadmap_cadence.py`. |
| FR-006 | Kind I docs/rules | s05, s06 | Обновление `mainrule.mdc`, `finish-doc-router.mdc`, `WORKFLOW.md`, `README.md`. |
| FR-007 | optional minimal resync helper (mark plan stale) | s02, s06 | Хелпер `mark_plan_stale` для инвалидации HOW без мутации §Epic. |
| US-001 | from-queue reports | s01, s06 | Отчёты по всем эпикам из `queue.yaml`. |
| US-002 | HIGH blocks resume | s03, s06 | Advance fail-closed при неразрешенном HIGH drift. |
| US-003 | after resync idle | s04, s06 | После сброса в `idle` разблокируется feature arm. |
| US-004 | no window in rules | s05, s06 | Запрет скользящих окон в правилах и документации. |
| TM-01 | from-queue finds pending queue epic | s01, s06 | Обнаружение эпиков очереди через `--from-queue`. |
| TM-02 | HIGH without resync blocks | s03, s06 | Блокировка продвижения без evidence. |
| TM-03 | after reset feature advances | s04, s06 | Переход к следующей фиче после сброса в idle. |
| TM-04 | Kind I no sliding window | s05, s06 | Отсутствие sliding window терминологии. |
| AC+ | from-queue works; HIGH blocks; reset restores feature lane; rules document cadence without window | s01, s02, s03, s04, s05, s06 | Полная поддержка resync tail, блокировки HIGH и сброса в idle. |
| AC− | no resume on raw HIGH; no §Epic mutation; no reintroduce window; no re-implement 092/093 executors | s01, s02, s03, s04, s05, s06 | Отсутствие обходных путей и неизменность промптов §Epic. |

## Stages coverage

| Stage | Plan section | sNN |
| :--- | :--- | :--- |
| 1. from-queue reconcile + tests | plan.md §Steps #1, FR-001, US-001, TM-01 | s01 |
| 2. cadence resync phase + evidence | plan.md §Steps #2, FR-002, FR-007 | s02 |
| 3. resume gate | plan.md §Steps #3, FR-003, US-002, TM-02 | s03 |
| 4. reset idle | plan.md §Steps #4, FR-004, US-003, TM-03 | s04 |
| 5. Kind I docs | plan.md §Steps #5, FR-006, US-004, TM-04 | s05 |
| 6. E2E: block_done → HIGH → block → resync → feature | plan.md §Steps #6, FR-005, Sunset | s06 |

## Outcome map

| Capability / Outcome | sNN | Verification |
| :--- | :--- | :--- |
| Reconcile всей очереди через CLI/API `--from-queue` | s01 | `bin/pytest loop/tests/test_reconcile_spec.py -k test_reconcile_from_queue` |
| Фиксация `ResyncEvidence` на SoT `cadence.yaml` и хелпер `mark_plan_stale` | s02 | `bin/pytest loop/tests/test_roadmap_cadence.py -k test_resync_evidence` |
| Fail-closed resume gate в `roadmap_advance` при наличии HIGH drift | s03 | `bin/pytest loop/tests/test_roadmap_cadence.py -k test_advance_blocked_resync` |
| Сброс фазы в `idle` и обнуление счетчика (`reset_cadence_idle`) | s04 | `bin/pytest loop/tests/test_roadmap_cadence.py -k test_reset_cadence_idle` |
| Документация Kind I и правила workflow (запрет sliding window) | s05 | `bin/pytest loop/tests/test_roadmap_cadence.py -q` |
| Sunset inventory purge и сквозной E2E тест полного жизненного цикла | s06 | `bin/pytest loop/tests/test_roadmap_cadence.py -k test_full_cadence_lifecycle_e2e` |

## Replacement cleanup

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Post-hygiene resume without tail check | A | Обязательный аудит очереди через reconcile from-queue | s01, s06 | no | Удаляется прежний обход без проверки хвоста. |
| Resume on raw HIGH drift without resync evidence | B | Fail-closed gate в `roadmap_advance` | s03, s06 | no | Raw HIGH больше не пропускается без evidence. |
| tasks.md-only sweep as sole cadence exit | C | Расширение до reconcile всей очереди `queue.yaml` | s01, s06 | no | Очередь проверяется целиком. |
| Sliding window assumptions in rules/docs | I | Фиксация строгого цикла cadence (every-2) без sliding window | s05, s06 | no | Kind I cleanup полностью удаляется и фиксируется в s05 и s06. |

## Очередь шагов (BACK)

| Step | Shard YAML | Implement YAML | Creative | Wire Complete | Next Phase | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **s01** | [s01-reconcile-from-queue-api-and-cli.yaml](../yaml/steps/s01-reconcile-from-queue-api-and-cli.yaml) | [s01-reconcile-from-queue-api-and-cli.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s01-reconcile-from-queue-api-and-cli.yaml) | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-cadence-resync-phase-and-evidence-schema.yaml](../yaml/steps/s02-cadence-resync-phase-and-evidence-schema.yaml) | [s02-cadence-resync-phase-and-evidence-schema.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s02-cadence-resync-phase-and-evidence-schema.yaml) | no | no | BACK IMPLEMENT | completed |
| **s03** | [s03-roadmap-resume-gate-and-advance-enforcement.yaml](../yaml/steps/s03-roadmap-resume-gate-and-advance-enforcement.yaml) | [s03-roadmap-resume-gate-and-advance-enforcement.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s03-roadmap-resume-gate-and-advance-enforcement.yaml) | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-cadence-reset-idle-api-and-feature-unblock.yaml](../yaml/steps/s04-cadence-reset-idle-api-and-feature-unblock.yaml) | [s04-cadence-reset-idle-api-and-feature-unblock.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s04-cadence-reset-idle-api-and-feature-unblock.yaml) | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-workflow-rules-and-kind-i-documentation.yaml](../yaml/steps/s05-workflow-rules-and-kind-i-documentation.yaml) | [s05-workflow-rules-and-kind-i-documentation.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s05-workflow-rules-and-kind-i-documentation.yaml) | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06-legacy-fallback-purge.yaml](../../implement/T-HUB-094-roadmap-cadence-resync-tail/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |