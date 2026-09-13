# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-092-roadmap-cadence-foundation
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-12
**Режим:** BACK DECOMPOSE

Нарезка реализует фундамент ритма дорожной карты (roadmap cadence foundation): типизированный Single Source of Truth (`cadence.yaml` со схемой `roadmap-cadence/v1`), атрибут `kind` элементов очереди (по умолчанию `feature`), инкремент счётчика завершённых feature-эпиков с переходом в фазу `replan` и фиксацией пары `pair_ids` каждые 2 эпика (`every_n: 2`), защиту от повторного инкремента (идемпотентность), блокировку автоматического выбора нового feature-эпика в `roadmap_advance` пока `phase != idle`, CLI-команду `cadence-status` и финальный sunset purge (A+B+C+I). Всего 6 sNN (целевой диапазон 5–8).

## Requirements coverage

| Req ID | Plan FR text | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Schema + path cadence.yaml | s01, s06 | Pydantic схема `roadmap-cadence/v1` в `loop/schemas/roadmap_cadence.py` + канонический файл `memory-bank/back/roadmap/cadence.yaml`. |
| FR-002 | API load/save/on_feature_done/on_non_feature_done | s01, s02, s06 | Функции загрузки/сохранения и изменения состояния в `loop/roadmap_cadence.py`. |
| FR-003 | kind on queue; default feature | s02, s06 | Поддержка поля `kind` в нормализации очереди `loop/roadmap_queue.py` (default: `feature`). |
| FR-004 | Wire mark_done → cadence hook | s03, s06 | Вызов хука обновления cadence из `mark_queue_epic_done` с защитой от повторного инкремента. |
| FR-005 | Wire advance: block feature select if phase≠idle | s04, s06 | Блокировка выбора следующего feature в `roadmap_advance` при активной фазе cadence (`phase != idle`). |
| FR-006 | Tests + cadence-status CLI | s05, s06 | CLI-подкоманда `cadence-status` в `loop/context_loop.py` и юнит-тесты. |
| FR-007 | Stub hooks/docs pointer: full block in 093/094 (не implement их) | s05, s06 | Документация и стабы хуков перехода к блоку REPLAN/Refactor (реализация в follow_up: T-HUB-093-roadmap-cadence-replan-refactor-block и follow_up: T-HUB-094-roadmap-cadence-resync-tail). |
| US-001 | Typed cadence load/save | s01, s06 | Fail-closed при невалидном YAML или неизвестной фазе. |
| US-002 | feature ++ / refactor no ++ | s02, s03, s06 | Инкремент счётчика только для `kind == feature`. |
| US-003 | 2 done → phase replan, pair len 2 | s02, s03, s06 | Переход в `phase: replan`, заполнение `pair_ids` списком из 2 эпиков. |
| US-004 | mid-block no new feature arm | s04, s06 | Запрет армирования 3-го feature-эпика в разгаре cadence-блока. |
| NFR-001 | Fail-closed corrupt SoT | s01, s06 | Ошибка валидации при повреждённом `cadence.yaml`. |
| NFR-002 | Idempotent mark | s03, s06 | Повторный вызов `mark_queue_epic_done` для уже завершённого эпика не увеличивает счётчик. |
| Out of scope | Исполнение REPLAN/Refactor блока | — | follow_up: T-HUB-093-roadmap-cadence-replan-refactor-block |
| Out of scope | Reconcile from-queue + resync tail + Kind I | — | follow_up: T-HUB-094-roadmap-cadence-resync-tail |

## Stages coverage

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| 1. Schema + cadence.yaml + load/save API | plan.md §Target layout & Technology axiom | s01 |
| 2. Queue kind + counter logic + replan transition | plan.md §Target layout & FR-002, FR-003 | s02 |
| 3. mark_done hook wire + idempotency | plan.md §Target layout & FR-004, NFR-002 | s03 |
| 4. roadmap_advance gate + pause feature selection | plan.md §Target layout & FR-005, US-004 | s04 |
| 5. cadence-status CLI + Kind I instruction surfaces | plan.md §Target layout & FR-006, FR-007 | s05 |
| 6. legacy-fallback-purge (A+B+C+I) | plan.md §Replacement / sunset & transition gate | s06 |

## Outcome map

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Typed cadence SoT (`roadmap-cadence/v1`) с fail-closed валидацией (US-001, NFR-001) | s01, s06 |
| Разделение типов эпиков через `kind` (feature vs refactor/other) и корректный учёт (US-002, FR-003) | s02, s06 |
| Автоматический переход в `phase: replan` с фиксацией пары эпиков `pair_ids` каждые 2 feature done (US-003, FR-002) | s02, s03, s06 |
| Идемпотентность вызова `mark_queue_epic_done` без ложных повторных инкрементов (NFR-002, FR-004) | s03, s06 |
| Строгая блокировка выбора нового feature-эпика в `roadmap_advance` при активном cadence (US-004, FR-005) | s04, s06 |
| Удобная CLI-диагностика состояния ритма (`cadence-status`) и выверка инструкций (FR-006, FR-007) | s05, s06 |
| Полное устранение устаревших fallback-путей и безусловного выбора фич без cadence-проверки | s06 |
| Out of scope: авто-армирование REPLAN/Refactor блока | follow_up: T-HUB-093-roadmap-cadence-replan-refactor-block |
| Out of scope: синхронизация очереди и хвост resync | follow_up: T-HUB-094-roadmap-cadence-resync-tail |

## Replacement cleanup

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Безусловный выбор следующего feature в `roadmap_advance` | A | Проверка `cadence.phase == idle` перед выбором feature | s04, s06 | no | Блокировка выбора feature при активном блоке. |
| Элементы очереди без явного `kind` | A | `kind: feature` по умолчанию в нормализаторе | s02, s06 | no | Поддержка `kind` на всех записях очереди. |
| `entrypoints/deploy` (n/a — те же CLI/хуки) | B | n/a — нет замен entrypoint/deploy | none | no | n/a for deploy |
| Необязательный (optional) cadence / тихий пропуск при отсутствии файла | C | Fail-closed загрузка `cadence.yaml` | s01, s06 | no | Запрет fallback-обхода cadence. |
| Старые инструкции roadmap-advance без упоминания cadence-гейта | I | Актуализация `loop/WORKFLOW.md` и документации | s05, s06 | no | Указание на роль cadence и follow-up эпики. |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-cadence-schema-and-sot-api.yaml](../yaml/steps/s01-cadence-schema-and-sot-api.yaml) | [s01-cadence-schema-and-sot-api.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s01-cadence-schema-and-sot-api.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-queue-item-kind-and-counter-logic.yaml](../yaml/steps/s02-queue-item-kind-and-counter-logic.yaml) | [s02-queue-item-kind-and-counter-logic.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s02-queue-item-kind-and-counter-logic.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-mark-done-cadence-wire-and-idempotency.yaml](../yaml/steps/s03-mark-done-cadence-wire-and-idempotency.yaml) | [s03-mark-done-cadence-wire-and-idempotency.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s03-mark-done-cadence-wire-and-idempotency.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-roadmap-advance-gate-and-pause.yaml](../yaml/steps/s04-roadmap-advance-gate-and-pause.yaml) | [s04-roadmap-advance-gate-and-pause.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s04-roadmap-advance-gate-and-pause.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-cadence-status-cli-and-instruction-surfaces.yaml](../yaml/steps/s05-cadence-status-cli-and-instruction-surfaces.yaml) | [s05-cadence-status-cli-and-instruction-surfaces.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s05-cadence-status-cli-and-instruction-surfaces.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06-legacy-fallback-purge.yaml](../../implement/T-HUB-092-roadmap-cadence-foundation/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**Следующий режим после завершения дерева:** BACK ANALYZE. `ANALYZE deferred` не используется.
