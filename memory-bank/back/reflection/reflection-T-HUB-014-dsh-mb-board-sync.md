---
schema: epic-reflect/v1
epic_id: T-HUB-014-dsh-mb-board-sync
task_id: T-HUB-014
date: "2026-08-29"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-014-dsh-mb-board-sync

## Итог

Эпик реализовал one-way синхронизацию memory-bank → DSH Task Board для зарегистрированных рабочих пространств. Контур включает discovery eligible workspaces, стабильную идентичность карточек и machine-readable metadata `mb-board-card/v1`, чтение pending/in_progress work items из decompose index, lifecycle gate cards, diff/orchestration, HTTP/Fake/Ledger-клиенты, CLI `sync`/`status`/`--dry-run`, документацию и fail-closed диагностику.

Первичный аудит выявил три отклонения: DONE не архивировал все оставшиеся mb-карточки эпика, `sync_generation` создавал generation-only updates при повторном неизменном sync, а ошибки выбора ROADMAP подавлялись как пустой список. Append-only remediation steps s09–s11 закрыли эти findings. Отдельные QA BUGFIX-циклы также исправили строгую проверку пути implement step для `@verify` и lint board-sync surfaces.

Финальный BACK QA завершён с `verdict: pass`, пустыми `issues`, `blockers` и `fix_plan`; reviewer подтвердил AC+/AC−, integration paths и security spot-check. Все s01–s11 имеют `status: completed` в каноническом decompose `index.yaml`. REFLECT не изменяла code surfaces: `code_changed: no`.

Границы сохранены: board остаётся downstream projection и не становится SoT; sync не запускает arm/loop/roadmap advance и не записывает статусы обратно в memory-bank; внешний DSH network не требовался для QA, поскольку HTTP-контракт покрыт клиентскими тестами и fail-closed проверками.

## vs plan / decompose

| Требование / outcome | Покрытие | Статус |
|---|---|---|
| US-001 / FR-001: discovery зарегистрированных eligible workspaces | s02; QA AC+ | ✅ |
| FR-002 / FR-003 / FR-008 / FR-012: card model, stable id, workspace/project metadata и `card_kind` parser round-trip | s01; QA AC+ | ✅ |
| FR-002 / SC-001: pending/in_progress steps → `mb-*` cards с корректным status mapping | s03; QA AC+ | ✅ |
| FR-013–FR-017: CLARIFY/ANALYZE/PLAN/DECOMPOSE/ROADMAP и post-implement lifecycle gates | s04, s09, s11; QA AC+ | ✅ |
| FR-005 / FR-006 / FR-010: create/update/archive diff и unchanged repeat no-op | s05, s09, s10; QA AC+ | ✅ |
| FR-009 / NFR fail-closed: TaskBoardClient, Fake/Ledger и HttpHostClient | s05–s06; QA AC− и security spot-check | ✅ |
| FR-007: `sync`, `status`, `--dry-run`, workspace filter и `--host-url` | s07; QA AC+ | ✅ |
| FR-011 / FR-018: README, prompt builder и gate/step UX | s08; QA AC+ | ✅ |
| AC−: no board-to-memory-bank write-back, no arm/loop side effects, non-mb preservation | s04–s11; QA AC− | ✅ |
| NFR: malformed workspace/index/HTTP/roadmap input fails closed with surfaced diagnostics | s03, s06, s11; QA AC+ и §0.11 | ✅ |
| Audit F1: DONE archive-all | s09; final QA | ✅ |
| Audit F2: generation-only update suppression | s10; final QA | ✅ |
| Audit F3: explicit roadmap selector diagnostics | s11; final QA | ✅ |
| Replacement cleanup | greenfield board-sync package; legacy replacement не требовался | ✅ |

Первоначальная декомпозиция s01–s08 была расширена append-only remediation shards s09–s11 по результатам AUDIT. Все три audit finding получили отдельный implement artifact, тестовые checkpoints и последующую проверку в полном QA; completed shards не переписывались.

## Successes

- Board-sync разделён на небольшие контуры: registry, card model, memory-bank scan, gate scan, diff, clients, sync и CLI. Это упростило локальную проверку и сохранило явные границы ответственности.
- Стабильная identity и metadata позволяют отличать управляемые `mb-*` карточки от manual/non-mb карточек и не превращать board в источник истины.
- Fail-closed обработка corrupt workspace/index, HTTP transport/non-2xx/invalid payload, lock conflict и roadmap configuration errors не скрывает обязательные зависимости под пустым успехом.
- DONE archive-all ограничен matching workspace/role/epic и сохраняет карточки другого эпика и non-mb карточки.
- Generation metadata сохранена для фактических create/update, но исключена из semantic equality; повторный неизменённый sync становится no-op.
- Lifecycle gates используют существующий `epic.reduce_epic_lifecycle`, поэтому board projection не изобретает независимую state machine и не добавляет arm/loop side effects.
- CLI dry-run и offline ledger mode дают проверяемый локальный путь без необходимости поднимать внешний DSH host; документация явно фиксирует ограничения offline режима.
- Полный backend suite и targeted board-sync suite запускались вместе с применимым scoped lint, compile и diff checks. QA подтвердил не только positive paths, но и negative/security cases.
- Audit findings были закрыты через отдельные s09–s11, а QA failures — через точечные bugfix artifacts без ослабления stop-gate или fail-closed контрактов.

## Problems

- Первичная реализация не полностью покрыла plan intent: AUDIT обнаружил три findings. Это было исправлено в текущем эпике, но показывает, что DONE/archive-all, semantic idempotency и error-channel paths нужно проверять до первого QA.
- Первый QA был красным: два stop-gate regression tests и board-sync lint gate потребовали отдельных BUGFIX проходов. После исправлений targeted и полный suite стали зелёными.
- `events.jsonl` содержит 14 событий (`audit_done`, `qa_fail`, `bugfix_done`, `qa_pass`), но не содержит machine-readable `implement_done` для s01–s11. Реальный progress восстанавливается из implement shards и delivery log, однако orchestration timeline неполон.
- QA remediation была конечной, но telemetry не объясняет компактно, почему конкретный `qa_fail` сменился на `bugfix_done`, а `last-session.retry_count` смешивает resume/retry сигнал с реальным progress.
- `.claude/runtime/epic/state.json` сообщает `state_rebuilt: true`, а текущий `checkpoint.json` находится в transient `BACK/REFLECT`, `stage: prepared`; `last-session.json` сохраняет предыдущий `BUGFIX`, `retry_count: 2`, `resume_dirty: false`. Это не product failure, но требует ручной интерпретации.
- Runtime dirty snapshot содержит широкий набор изменений hub checkout, включая поверхности других эпиков и pre-existing work. QA ограничил проверку scope T-HUB-014; автоматического ownership summary нет.
- `.venv/bin/graphify` отсутствует в tooling hub checkout, поэтому graphify query/update не выполнялись. Применён предусмотренный hub-repository inventory fallback; это ограничение среды, не незакрытый AC.
- Исторические lint findings в `loop/context_loop.py` и shell wrapper не входят в Fix plan board-sync cleanup. Scoped lint это явно зафиксировал; расширять cleanup за пределы эпика не потребовалось.

## Lessons

1. Для board projections нужно заранее разделять semantic card content и operational metadata. Счётчик поколения не должен сам по себе вызывать update.
2. Terminal lifecycle должен иметь отдельный explicit signal. DONE archive-all нельзя выводить только из текущего desired set, иначе исчезнувшие активные cards останутся на board.
3. Любая обязательная конфигурация, включая roadmap queue, должна иметь error channel. `[]` допустим только для честного отсутствия work, но не для swallowed selector failure.
4. Downstream sync следует строить как one-way projection с узкой ownership identity; preservation manual/non-mb cards должен быть отрицательным acceptance case.
5. Для L3 tooling-фичи полезна связка targeted tests → scoped lint → полный backend suite → reviewer. Она быстрее локализует дефект и не позволяет targeted green скрыть общую регрессию.
6. Audit findings лучше превращать в отдельные append-only remediation shards. Так сохраняются исходный gap, delta, checkpoint evidence и история повторного QA.
7. Runtime orchestration telemetry нужно рассматривать как отдельный quality layer: успешный product outcome не компенсирует отсутствие implement events, ownership summary и точного retry/advance semantics.

## Improvements

- Перед первым QA добавить в implement workflow обязательные pre-QA checks для audit-sensitive paths: terminal archive-all, semantic idempotency и malformed configuration diagnostics.
- Для loop/hooks добавить `implement_done` emission на `finalize-step` или bounded batch event с перечислением завершённых shards.
- Разделить runtime counters на `qa_fail`, `bugfix_advance`, `retry_without_advance`, `external_abort`, `state_rebuild` и `resume_dirty`; не использовать один `retry_count` для разных причин.
- Синхронизировать `last-session.json`, `checkpoint.json` и `state.json` на QA → REFLECT переходе и маркировать stale/transient snapshot явно.
- Добавить scoped ownership summary для dirty snapshot, отделяя изменения текущего эпика от pre-existing и чужих эпиков.
- Добавить bounded session diagnostic summary с abort/halt/role-drift/same-step markers вместо необходимости сканировать raw session log.
- В QA workflow зафиксировать graphify availability preflight для hub/tooling repositories и сохранять `unavailable/skip` как нормальное ограничение среды.
- Не расширять текущий scope в новый implementation shard: frontend runners, board-to-memory-bank write-back, arm/loop launch и внешний DSH deployment относятся к другим эпикам или явно исключены.

## Orchestration signals

| Источник | Наблюдение | Интерпретация |
|---|---|---|
| `memory-bank/back/events/T-HUB-014-dsh-mb-board-sync/events.jsonl` | 14 событий: seq1 `audit_done`; seq2–5 `qa_fail`; seq6–7 `bugfix_done`; seq8 `qa_fail`; seq9–13 `bugfix_done`; seq14 `qa_pass` | Были реальные конечные QA remediation cycles с advance; бесконечного same-step loop не обнаружено, но implement timeline отсутствует |
| `memory-bank/back/qa/T-HUB-014-dsh-mb-board-sync/qa-20260829-dsh-mb-board-sync.yaml` | `verdict: pass`; `issues: []`; `blockers: []`; `fix_plan: []`; reviewer PASS | QA gate закрыт, повторный BUGFIX не требуется |
| `memory-bank/back/plan/decompose-T-HUB-014-dsh-mb-board-sync/index.yaml` | s01–s11 имеют `status: completed` | Каноническая implement queue исчерпана |
| `.claude/runtime/epic/last-session.json` | `status: completed`, `outcome: clean`, `exit_code: 0`, `retry_count: 2`, `resume_dirty: false`, `abort_kind: null`, последний `step_id: BUGFIX` | Завершение чистое; retry count и stale step требуют улучшения telemetry, но не указывают на текущий abort |
| `.claude/runtime/epic/checkpoint.json` | identity `BACK/REFLECT`, `stage: prepared`, `retry_count: 0`, `status: active` | Подготовка текущего REFLECT шага; не product failure |
| `.claude/runtime/epic/state.json` | `state_rebuilt: true`, diagnostic `state_rebuilt`, `halt_reason: null`, phase `REFLECT` | Восстановление runtime состояния без halt; сигнал наблюдаемости |
| `runtime/dev-hub/epic/session-21.log` и `session-21-t2.log` | финальные result records имеют успешный статус; bounded marker scan не выявил отдельного actionable abort/halt или role/phase drift | Текущий QA/FINISH путь завершён clean; raw logs не переносятся в reflection целиком |
| Runtime dirty snapshot | широкий список изменённых файлов, включая board-sync, hooks, docs и pre-existing hub surfaces | Нужен ownership-aware snapshot; QA проверял только заявленный epic scope |
| Фактический lifecycle | BACK IMPLEMENT s01–s08 → BACK AUDIT → BACK IMPLEMENT s09–s11 → BACK QA/BUGFIX remediation → BACK QA PASS → BACK REFLECT | Role/phase drift и пропуск обязательного QA не обнаружены; QA failures возвращали работу в owning BUGFIX |

**Вывод layer B:** orchestration довела эпик от первичного AUDIT через три remediation shard и конечные QA/BUGFIX циклы к PASS и REFLECT. Сигналы неполного event timeline, rebuilt/stale snapshots, неоднозначного retry count и широкого dirty snapshot относятся к качеству loop/hooks; они не переоткрывают закрытый product scope.

## Promote candidates

| Сигнал | → | Решение |
|---|---|---|
| Нет `implement_done` для s01–s11 | → loop/hooks | Добавить emission в `finalize-step`; текущий event log задним числом не переписывать |
| `retry_count` смешивает retry и clean resume | → loop/hooks | Ввести structured retry/advance/abort counters и progress classification |
| `state_rebuilt: true` и stale/transient step snapshots | → loop/hooks | Синхронизировать runtime snapshots и добавить bounded diagnostic summary |
| Dirty snapshot смешивает scope эпика и чужие изменения | → loop/hooks | Добавить ownership-aware dirty summary для QA/REFLECT |
| Первичный AUDIT с F1–F3 был закрыт s09–s11 | → workflow | Сохранить audit → remediation shards → повторный QA как канонический remediation path |
| Первый QA выявил stop-gate и lint regressions | → workflow | Оставить targeted + scoped lint перед полным suite и reviewer gate |
| Нет frontend surface и нет board write-back/arm scope | → skip | Не запускать frontend tests и не создавать новые shards в T-HUB-014 |
| Graphify binary отсутствует в hub checkout | → skip | Зафиксировать N/A inventory fallback; не блокировать завершённый tooling epic |
| Архивация должна выполняться после остановки runner | → skip | Не запускать ARCHIVE NOW внутри текущей REFLECT-сессии |

## Метрики

- Шагов: 11 / 11 completed (100%).
- Первичный AUDIT: 3 findings; remediation s09–s11 закрыла F1–F3.
- Финальный QA: `verdict: pass`; issues 0; blockers 0; fix_plan 0.
- Targeted board-sync suite: 53 passed.
- Full backend suite: 7758 passed, 181 skipped, 48 warnings.
- Applicable Ruff: pass для `loop/board_sync` и board-sync tests.
- Compile и `git diff --check`: pass.
- Event log: 14 событий — 1 `audit_done`, 3 `qa_fail`-событий группой seq2–5 и seq8, 7 `bugfix_done`, 1 `qa_pass`; implement events отсутствуют.
- Runtime: `last-session.retry_count: 2`, `resume_dirty: false`, `abort_kind: null`, `state_rebuilt: true`; текущий checkpoint REFLECT `retry_count: 0`.
- Frontend tests: неприменимы для BACK tooling scope.
- Graphify: unavailable в hub checkout.
- `code_changed` этой REFLECT-сессии: no.

## Next

Эпик завершён с PASS. После handoff фиксируется отдельная строка `EPIC_DONE` и runner останавливается. Архивация артефактов выполняется вручную вне текущей REFLECT-сессии после остановки runner; ARCHIVE NOW в этой сессии не запускается.
