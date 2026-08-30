---
schema: epic-reflect/v1
epic_id: T-HUB-015-dsh-board-arm-loop
task_id: T-HUB-015
date: "2026-08-29"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-015-dsh-board-arm-loop

## Итог

Эпик реализовал board-driven arm + loop для `mb-board-card/v1`: разбор и fail-closed валидацию карточек, точные argv с precedence `env > preset > default > bare`, проверку step mismatch, последовательный arm → loop pipeline, subprocess execution result, CLI `hub-board arm|loop|arm-loop`, bridge между DSH Host и Python, workspace filter/model controls, документацию и install/regression coverage.

После первичной реализации аудит выявил пять отклонений. Append-only remediation s11–s15 добавили запись execution result в board/ledger, подключили live stock-run deny/redirect path, вывели workspace options из Host `workspace.list`, протянули `model_source`/`model_env` до Host UI и включили строгую ROADMAP/config authorization. Дополнительный bugfix исключил `reason_code` из явных ROADMAP target keys, чтобы диагностическая причина не могла стать целью эпика.

Финальный BACK QA завершён с `verdict: pass`, пустыми `issues`, `blockers` и `fix_plan`; reviewer gate также дал `VERDICT: PASS`. Канонический `index.yaml` показывает s01–s15 `completed`. REFLECT не меняла product/code surfaces: `code_changed: no`.

Границы сохранены: board остаётся downstream projection, arm/loop использует существующий pipeline, не выполняется silent stock-run fallback для `mb-*`, ROADMAP advance остаётся opt-in, а board execution records не становятся записью в product memory-bank. Frontend runner не запускался: у TypeScript package нет package scripts, а BACK QA подтверждал Python/bridge source contracts и полный backend suite.

## vs plan / decompose

| Требование / outcome | Покрытие | Статус |
|---|---|---|
| AC+1 / FR-001: `mb-board-card/v1` metadata parser и fail-closed invalid input | s02; metadata tests | ✅ |
| AC+2 / AC+12 / FR-002: exact arm/loop argv, model whitelist и precedence | s03, s14; argv/CLI/UI evidence | ✅ |
| AC+3 / AC+4 / FR-004: arm updates activeContext and rejects step mismatch | s04; arm tests and diagnostic evidence | ✅ |
| AC+5 / FR-005: arm-loop short-circuits before loop on arm failure | s06; pipeline tests | ✅ |
| AC+6 / FR-003: loop execution maps success/failure/timeout/spawn errors | s05, s11; execution-result and CLI tests | ✅ |
| AC+7 / AC+8 / AC−7: live `mb-*` stock Run deny/redirect with non-mb passthrough | s08, s12; mounted intercept source contract and bridge tests | ✅ |
| FR-007 / AC+10: board CLI commands, help, diagnostics and dry-run behavior | s07; CLI tests | ✅ |
| AC+11 / AC+13 / FR-012: Host workspace.list, All option, persistence and metadata workspace filter | s09, s13; UI/filter/bridge tests and source controls | ✅ |
| FR-007 / FR-015 / SC-008: effective model source reaches execution record and Host UI | s03, s14; Python/Host/UI propagation evidence | ✅ |
| FR-008 / AC−3 / Constitution MUST-5: ROADMAP authorization and strict bridge config | s04, s15; authorization/config tests and reason-code regression | ✅ |
| FR-007 / AC+9 / AC+14: runbook, install flow and regression coverage | s10; README/install evidence and QA suite | ✅ |
| AC−1…AC−6: no board-to-memory-bank write-back, no hidden arm/loop side effects, bounded inputs and non-mb preservation | s05–s15; final QA integration/security checks | ✅ |
| Audit findings F1–F5 | s11–s15 plus roadmap reason-code bugfix; repeat QA | ✅ |

Первичный queue из s01–s10 был расширен отдельными remediation shards, а completed artifacts не переписывались. Канонический status взят из `index.yaml`; историческая пояснительная строка в `index.md` о том, что s11–s15 остаются pending, теперь устарела относительно YAML index и финального QA, но не меняет канонический прогресс.

## Successes

- Каждый из пяти audit findings получил отдельный атомарный shard, тестовые checkpoints и повторную проверку; исправления не были замаскированы переписыванием исходных artifacts.
- Arm и loop остались одной последовательной fail-closed цепочкой: ошибка arm не вызывает loop, а результат loop не теряется при записи execution record или при optional sync.
- Повторная проверка покрыла не только happy path, но и non-zero exit, timeout, spawn error, malformed metadata/config, disabled bridge, step mismatch, запрещённый ROADMAP advance и reason-code-only карточку.
- Stock-run replacement стал live wiring: `mb-*` не попадает в обычный Host runner, тогда как non-mb passthrough сохранён.
- Model source и workspace source теперь наблюдаемы на границе Host/UI, а не остаются только внутренними Python вычислениями.
- Полный backend suite прошёл без failures, включая scoped board-launch/board-sync regression и полный repository run; `git diff --check` прошёл.
- Stop-gate не был ослаблен: QA failures возвращали работу в bugfix, а REFLECT начался только после финального QA pass.

## Problems

- Первичная реализация не закрыла все plan outcomes: до первого финального QA отсутствовали execution recording, live stock-run registration, Host workspace.list adapter, model-source response wiring и ROADMAP/config enforcement. Ранний AUDIT и последующая remediation это исправили, но pre-QA coverage была недостаточной.
- В течение эпика было три `qa_fail` события и два `bugfix_done` события. Циклы были конечными и привели к `qa_pass`, однако event log не содержит machine-readable причины каждого fail→fix перехода.
- `events.jsonl` фиксирует audit/QA/bugfix milestones, но не содержит `implement_done` для s01–s15; фактический прогресс приходится восстанавливать из delivery log и implement shards.
- Runtime snapshot сообщает `state_rebuilt: true`, `last-session.retry_count: 1`, предыдущую фазу `BUGFIX` и `resume_dirty: false`, тогда как текущий checkpoint уже подготовлен для `BACK/REFLECT`. Это ожидаемый переход состояния, а не product failure, но snapshot плохо разделяет resume/retry и реальный advance.
- Отсутствие root graphify artifacts в hub checkout потребовало предусмотренного inventory fallback. Это не блокировало tooling epic, но снижает автоматическую cross-file ориентацию.
- В decompose `index.md` осталась устаревшая историческая заметка о pending s11–s15; status SoT `index.yaml` корректен, но документационный дрейф может вводить в заблуждение при ручном чтении.

## Lessons

1. Для brownfield board/Host integration нужно проверять не только наличие helper-функций, но и регистрацию live handler в mount path. Source helper без event wiring не является выполненным контрактом.
2. Для каждого результата запуска следует заранее определять boundary contract: status, exit code, diagnostic code, bounded log reference и дополнительные effective settings должны переходить через CLI → Host → UI/record.
3. Диагностические поля нельзя использовать как authorization fields. ROADMAP target должен иметь отдельный explicit metadata contract, а `reason_code` должен оставаться только причиной результата.
4. Конфигурация с boolean authorization и runtime toggles должна валидироваться на обеих границах — Python и TypeScript — до регистрации маршрутов или выполнения side effect.
5. `tasks.md`, delivery log, event log и runtime snapshots выполняют разные функции. Их нужно проектировать как согласованные projections, а не рассчитывать, что один generic `retry_count` восстановит весь lifecycle.
6. Для tooling repository отсутствие graphify — штатный N/A сценарий; inventory fallback следует фиксировать явно, не превращая его в ложный blocker.

## Improvements

- До BACK QA добавить обязательный pre-QA integration checklist для live registration, Host RPC adapters, result propagation и authorization/error channels; запускать его вместе со scoped tests.
- Сделать event emission машинно-полным для implement completion и remediation: `implement_done`, `qa_fail` с reason/fix target, `bugfix_done` с advance marker и `qa_pass` с covered scope.
- Разделить runtime counters на `qa_fail`, `bugfix_advance`, `retry_without_advance`, `external_abort`, `state_rebuild` и `resume_dirty`; не перегружать `retry_count` несколькими смыслами.
- Добавить finish-time consistency check, который обнаруживает stale prose в `decompose/index.md`, если canonical `index.yaml` уже перевёл append-only shards в completed.
- Для DSH plugins сохранить source-contract tests на mount registration и config validation; при появлении package scripts добавить parent-only TypeScript test command в QA scope.
- Удерживать board execution records наблюдательными: они не должны становиться скрытым write-back в product memory-bank или заменять SoT.

## Orchestration signals

| Источник | Сигнал | Оценка |
|---|---|---|
| `events.jsonl` seq1 | `audit_done` после первичной очереди | Нормальный переход IMPLEMENT → AUDIT. |
| `events.jsonl` seq2–4 | Три `qa_fail` | Реальные remediation cycles; не same-step loop, поскольку затем последовали bugfix advances. |
| `events.jsonl` seq5–6 | Два `bugfix_done` | Bounded progress к исправлению QA findings; причины переходов недостаточно структурированы. |
| `events.jsonl` seq7 | `qa_pass` | Финальный QA gate пройден. |
| `last-session.json` | `status: completed`, `exit_code: 0`, `abort_kind: null`, `resume_dirty: false` | Чистое завершение последнего runtime session. |
| `last-session.json` | `step_id: BUGFIX`, `retry_count: 1` | Исторический snapshot предыдущей remediation-фазы; требует разделения retry/resume semantics. |
| `checkpoint.json` | `BACK/REFLECT`, `stage: prepared`, `retry_count: 0` | Ожидаемая подготовка текущего шага; role/phase drift не обнаружен. |
| `state.json` | `state_rebuilt: true`, diagnostic `state_rebuilt` | Runtime восстановил projection из источников; не product failure, но telemetry signal для улучшения hooks. |
| Session log | Нет подтверждённых `abort`, `halt`, `NEED_HUMAN`, same-step stall или dirty чужого эпика | Внешнего/человеческого стопа и бесконечного retry не обнаружено. |
| Delivery log + decompose index | s01–s15 имеют implement artifacts и canonical `completed` | Прогресс подтверждён несмотря на неполный event timeline. |

## Promote candidates

| Сигнал / кандидат | Решение | Обоснование |
|---|---|---|
| Live wiring helper без mount registration | → workflow | Добавить pre-QA live-surface/import audit для Host integrations. |
| Неполный event timeline и generic `retry_count` | → loop/hooks | Структурировать implement/remediation events и runtime counters. |
| `state_rebuilt` при чистом переходе в REFLECT | → loop/hooks | Показывать rebuild как отдельный diagnostic signal без ложного blocker. |
| Устаревшая prose-заметка в decompose index | → workflow | Добавить consistency check между YAML SoT и human-readable coverage notes. |
| Graphify отсутствует в hub checkout | → skip | Применён разрешённый N/A inventory fallback; текущий эпик не блокирует. |
| Frontend package без test scripts в BACK tooling scope | → skip | Frontend runner неприменим; не создавать искусственный frontend QA scope. |
| Архивация до остановки runner | → skip | ARCHIVE NOW не запускать внутри текущей REFLECT-сессии. |

## Метрики

- Шагов: 15 / 15 completed (100%).
- Первичный AUDIT: 5 findings — 2 high и 3 medium; remediation s11–s15 закрыла все findings.
- QA remediation: 3 `qa_fail` события, 2 `bugfix_done` события, затем `qa_pass`; итоговый QA `issues: 0`, `blockers: 0`, `fix_plan: 0`.
- Финальный scoped suite: 144 passed.
- Loop suite: 712 passed.
- Full repository suite: 7849 passed, 181 skipped, 48 warnings.
- `git diff --check`: pass.
- Runtime: `last-session.exit_code: 0`, `abort_kind: null`, `resume_dirty: false`, `retry_count: 1`; current checkpoint `REFLECT`, `retry_count: 0`; `state_rebuilt: true`.
- Frontend tests: неприменимы для текущего BACK tooling scope; package scripts отсутствуют.
- Graphify: N/A для hub checkout; inventory fallback зафиксирован в implementation artifacts.
- `code_changed` этой REFLECT-сессии: no.

## Next

Эпик завершён с PASS. После handoff фиксируется отдельная строка EPIC_DONE, runner останавливается. Архивация артефактов выполняется вручную вне текущей REFLECT-сессии после остановки runner; ARCHIVE NOW в этой сессии не запускается.
