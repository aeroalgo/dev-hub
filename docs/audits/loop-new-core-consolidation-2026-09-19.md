# Проект нового ядра Loop без дублирования логики

Дата: 2026-09-19  
Основание: [`loop-cutover-deletion-audit-2026-09-18.md`](loop-cutover-deletion-audit-2026-09-18.md)  
Срез кода: рабочее дерево после cutover  
Цель: определить, какие удалённые ответственности должны войти в новое ядро, а какие нельзя возвращать как отдельные подсистемы.

## Решение

Старое дерево не следует восстанавливать пофайлово. Оптимальное решение — оставить `loop/kernel` единственным владельцем доменной логики и перенести в него только проверенные контракты старых систем.

У нового ядра должны быть семь владельцев:

1. `LoopState` и `TransitionService` — единственная state machine и единственный writer текущего состояния.
2. `ContractRegistry` — единственная валидация межграничных payloads, identity, evidence и receipts.
3. `SessionSupervisor` и `RuntimeAdapter` — единственная классификация исхода запуска, retry, timeout, idle и model substitution.
4. `BoundaryDispatcher` — единственная decision boundary для hooks и runtime providers.
5. `ContextPolicy` — единый владелец read/search/tool/touch policy и actor-aware ledger.
6. `FinishTransaction` — единственный путь продвижения шага, индекса и generated context.
7. `FailureRecord`/`IncidentStore` — единственный путь хранения отказа и восстановления.

Hooks, Claude/Codex и CLI остаются тонкими transport/adapters. Они не должны содержать вторую реализацию этих семи обязанностей.

Это означает, что удалённые `context_loop.py`, `epic_transition.py`, `harness/hooks/epic/core.py`, `runner/orchestrator.py` и `session_resilience.py` не возвращаются как runtime-модули. Их поведение используется как источник требований и characterization tests, а не как готовые слои поверх нового ядра.

## Почему текущая минимальная замена недостаточна

Текущий код уже сделал правильный шаг: у него есть один cursor, атомарный lock, actor-aware context ledger и строгий Pydantic verdict. Но это пока не единый новый контракт:

| Наблюдение | Почему это ещё не решение причины |
|---|---|
| [`loop/kernel/engine.py`](../../loop/kernel/engine.py) сам вычисляет `_phase_after_queue` и `_finish_locked` | Фазовая политика зашита в коде и не покрывает старые ANALYZE/CREATIVE/decompose/role gates. Добавление очередного `if` будет новой заплаткой. |
| [`loop/kernel/model.py`](../../loop/kernel/model.py) содержит простой `Cursor` | В нём нет `phase_epoch`, typed failure, attempt identity, evidence identity и связи с предыдущей попыткой. Строковый `last_error` не является session contract. |
| [`loop/kernel/runtime.py`](../../loop/kernel/runtime.py) возвращает `RuntimeResult` | Он умеет запустить процесс, stream и timeout, но не различает idle/crash/API abort, model substitution, transient/permanent и не сохраняет полноценный attempt record. |
| [`loop/kernel/store.py`](../../loop/kernel/store.py) отдельно пишет cursor и `events.jsonl` | Между `write(cursor)` и `append_event()` нет общей transaction identity. После сбоя можно получить состояние и журнал, не соответствующие друг другу. |
| [`loop/kernel/verdict.py`](../../loop/kernel/verdict.py) валидирует только `loop-gate-verdict/v1` | Строгая wire-схема есть, но нет единого registry для checkpoint/handoff/finish/session/evidence и нет старой proof/fingerprint семантики. |
| [`loop/kernel/lifecycle.py`](../../loop/kernel/lifecycle.py) имеет свой `HookAction` и свою эвристику извлечения agent/message | Это уже второй decision shape рядом с удалённым `DecisionEnvelope`/`gate_runtime`. Если продолжать расширять его локально, появится новая hook-specific state machine. |
| `harness/hooks/context_ledger.py`, `context_ledger_adapters.py`, `touch_ledger.py` названы compatibility facade | Они допустимы только как временный transport shim. Если в них добавлять правила, canonical owner снова раздвоится. |
| [`harness/hooks/stop-gate.py`](../../harness/hooks/stop-gate.py) сейчас фактически пропускает событие | Финальная граница не должна решаться prompt-ом или shell exit code; она должна делегировать typed decision в ядро. |
| `.codex/hooks.json` подключает новые hooks, а `.claude/settings.json` не содержит hook registration | Provider parity нельзя оставлять ручным. Регистрация должна быть materialized из одного manifest и проверяться одинаковыми tests. |

## Карта ответственности: что переносить, а что не возвращать

| Удалённые owners в `HEAD^` | Что из них действительно нужно | Единственный новый owner | Решение по старому коду |
|---|---|---|---|
| `loop/context_loop.py`, `loop/epic_transition.py`, `harness/hooks/epic/core.py` | Полный граф фаз, gates, epoch, active-context projection, post-implement и DONE policy | `TransitionService` + `LoopState` + `ProjectionService` | Не возвращать три реализации. Перенести правила в typed phase graph и reducer. |
| `loop/roadmap_queue.py`, текущий `loop/kernel/index.py` | Нормализация decompose index и выбор следующего шага | `WorkPlanReader`; roadmap chaining — отдельный orchestration feature | Не держать две очереди и не копировать index в runtime state. Project index остаётся input, cursor хранит только текущую позицию. |
| `loop/schemas/*`, `gate_runtime.py`, `gate_receipt.py` и текущий `verdict.py` | Версионированные схемы, identity binding, immutable evidence и retry classification | `ContractRegistry` и `EvidenceService` | Текущий validator расширить и централизовать. Старые schema helpers не подключать рядом. |
| `loop/runner/session.py`, `runner/orchestrator.py`, `runner/ownership.py`, `runner/output.py`, `session_resilience.py` и текущий `runtime.py` | Provider-neutral запуск, bounded attempt, timeout/idle/crash, stream, model identity, предыдущий результат | `SessionSupervisor` + `RuntimeAdapter` | Не добавлять retry-ветки в CLI и hooks. `Runtime` становится I/O adapter, supervisor — владельцем смысла результата. |
| `harness/hooks/hook_dispatch.py`, `gate_runtime.py`, текущие `*-dispatch.py` и `lifecycle.py` | Нормализация event, одна decision boundary и provider-specific output | `BoundaryDispatcher` с `DecisionEnvelope` | Shell entrypoint только читает stdin, вызывает ядро и форматирует ответ Claude/Codex. |
| `harness/hooks/context_scope.py`, `pretool_policy.py`, `agent_policy.py`, текущий `ledger.py` и adapters | Read interval/hash, search allowlist, graphify exception, tool/agent policy, touch scope, test fingerprint | `ContextPolicy` поверх текущего `ContextLedger` | Текущий ledger сохранить как основу; policy расширять внутри одного сервиса, а не возвращать старый scope stack. |
| `loop/mb_load/*`, `loop/mb_finish/*`, `loop/mb_scaffold/*`, текущий `_render` | Load contract, finish evidence, atomic projection и ограниченный scaffold | `ContextProjection` + `FinishTransaction` | Load/finish не должны сами менять cursor. Scaffold — отдельная command, использующая те же схемы. |
| `loop/incidents/*` и текущий `last_error` | Durable failure, retry exhaustion, escalation и audit trail | `FailureRecord` в core; `IncidentStore` в recovery layer | Не возвращать Tier-1 runner до появления typed failure. Никакого нового fallback поверх `last_error`. |
| `loop/runtime_adapters/*`, `runtime_materializers/*`, текущие Claude/Codex classes | Общий adapter contract, manifest/parity и provider-specific command | `RuntimeAdapterRegistry` | Оставить два адаптера за одним интерфейсом; provider policy не должна проникать в transition logic. |
| `loop/stack_profiles/*` | Typed capability checks и execution evidence | `CapabilityService` | Подключить к finish contract после P0; не заменять typed evidence generic pytest-командой. |
| `loop/board_*`, `episodes`, `telemetry`, `dashboard`, `sunset_sidecar_store` | Внешняя синхронизация и наблюдаемость | P1/P2 projections | Не делать их вторым источником состояния и не блокировать ими базовую sequential state machine. |
| `loop/dag.py`, `loop/parallel/*` | DAG и безопасный parallel mode | Отдельный `ParallelCoordinator` после sequential core | До возврата overlap/worktree/status contracts parallel должен быть явно выключен. |
| `loop/janitor/*` | Bounded cleanup и repair | Отдельный `Janitor` после incident layer | Только whitelist + dry-run; не прятать cleanup в finish/retry. |

## Целевая топология нового ядра

```text
                    project artifacts
                 decompose index / gates
                           │
                           ▼
                 ┌────────────────────┐
                 │   WorkPlanReader   │
                 └─────────┬──────────┘
                           │ input only
                           ▼
┌──────────────┐   ┌────────────────────┐   ┌──────────────────────┐
│ Runtime      │──▶│ SessionSupervisor  │──▶│ ContractRegistry      │
│ Adapter      │   │ attempt/outcome    │   │ schema/identity       │
└──────────────┘   └─────────┬──────────┘   └──────────┬───────────┘
                              │                         │
                              ▼                         ▼
                      ┌────────────────────────────────────┐
                      │ TransitionService / FinishTransaction│
                      │ LoopState reducer + evidence checks │
                      └──────────────┬─────────────────────┘
                                     │ one transaction
                                     ▼
                      ┌────────────────────────────────────┐
                      │ RuntimeStore                        │
                      │ state projection + append-only log  │
                      └──────────────┬─────────────────────┘
                                     │ projections
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
             activeContext.md                    events/receipts

Hooks = transport adapters only:
PreTool/PostTool → ContextPolicy
SubagentStart/Stop/Stop → BoundaryDispatcher
Claude/Codex output → provider formatter
```

Главный инвариант: стрелки в ядро идут в одну сторону. `activeContext`, hook output, CLI status и dashboard читают projection; ни один из них не может сам продвинуть фазу.

## Канонические новые контракты

Не нужно версионировать каждый внутренний Python dataclass. Версия нужна только на границе persistence или процесса. Предлагаемый registry:

| Контракт | Назначение | Что устраняет |
|---|---|---|
| `loop-state/v2` | `epic`, `role`, `phase`, `step`, `phase_epoch`, `loop_session_id`, `attempt`, `status`, owner и typed failure | Разные `cursor`, `epic_state`, checkpoint и active-context identity |
| `loop-transition/v1` | `before_revision`, `event`, `after_revision`, `source`, `reason`, `idempotency_key` | Неявные переходы через CLI, hooks и ручное изменение index |
| `loop-session-attempt/v1` | runtime/model, command identity, timestamps, exit, abort code, idle/timeout, log digest, previous attempt | Строковый `RuntimeResult` и разрозненный retry |
| `loop-gate-decision/v2` | identity, agent, verdict, evidence refs, fingerprint, receipt digest, authority и timestamp | Одновременные `verdict`, `gate_runtime` и verifier receipt |
| `loop-decision-envelope/v1` | event, allow/deny/retry/record, diagnostic codes, receipt и transition ref | Разные `HookAction`, `DecisionEnvelope` и provider JSON |
| `loop-context-decision/v1` | actor, canonical path, content hash, requested/allowed/cached intervals, policy version | Раздельные старые/new read policy и неявный reread |
| `loop-finish-receipt/v1` | evidence, changed paths, index revision, state revision и transaction id | Непроверенное `finish` и неатомарный active context |
| `loop-failure/v1` | category, retryability, attempt, cause, remediation, escalation | `last_error` как единственная диагностика |

Для уже пригодных семантик можно сохранить `context-ledger/v1` и `loop-touch-ledger/v1` как внутренние форматы. Менять version только ради переименования не нужно. Но их запись и решение должны идти через `ContextPolicy`, а не через compatibility-модули.

## Что считать старым и новым контрактом

Переход должен быть односторонним:

1. Новый core принимает только canonical contracts из registry.
2. На transport boundary допускается один `LegacyDecoder` для уже запущенных Claude/Codex/CLI клиентов.
3. `LegacyDecoder` только переводит payload `v1 → canonical`; он не принимает решения, не пишет state и не делает retry.
4. После нормализации весь путь проходит через один validator, один reducer и один store.
5. State migration выполняется один раз под lock, пишет `migration receipt`, затем старый state становится read-only. Двойной записи old/new не должно быть.
6. После завершения cutover legacy decoder удаляется; тесты нового ядра больше не импортируют старые owners.

Таким образом, временное принятие старого wire payload не означает параллельную поддержку двух логик. Это один адаптер на входе и один canonical contract внутри.

## State machine и атомарный переход

Новый reducer должен быть конфигурационным, но не расплывчатым. `phase-registry` задаёт допустимые фазы и обязательные gates, а `TransitionService` остаётся единственным исполнителем правил.

Базовый граф:

```text
START
  → [PLAN/DECOMPOSE/ANALYZE/CREATIVE, если активированы правилами]
  → IMPLEMENT/TASK/REFACTOR/BUGFIX
  → AUDIT
  → QA ──FAIL/BLOCKED──▶ BUGFIX ──▶ QA
  → DONE
```

У каждой фазы есть `finish_contract`: требуемые artifacts, agent/evidence, capability checks, допустимый next phase и правило изменения index. Поэтому добавление новой фазы не требует ещё одного `if` в engine.

Commit одного перехода должен выглядеть так:

1. Под lock прочитать `LoopState` и его revision.
2. Проверить identity, schema, current phase, evidence, artifact fingerprints и expected revision.
3. Рассчитать один `Transition` и `FinishReceipt`.
4. Записать в append-only journal один transaction record с `tx_id`, before/after revision и checksum.
5. Атомарно заменить state projection и generated context из результата этой транзакции.
6. Только после commit обновить project index, если это часть `finish_contract`; обновление тоже получает `tx_id` и проверку revision.
7. При старте восстановить незавершённую transaction из journal, а не угадывать по `last_error`.

`events.jsonl`, session logs, receipts и active context остаются полезными проекциями/доказательствами, но ни один из них не становится альтернативным current state.

## Session contract: настоящая замена retry-заплаток

`RuntimeAdapter` должен знать только, как подготовить и запустить Claude/Codex. `SessionSupervisor` должен знать, что означает результат:

- `completed_without_commit` — процесс завершился, но finish не принят;
- `transient_transport` — временный stream/API/process сбой;
- `idle_timeout` и `hard_timeout` — разные причины;
- `user_interrupt` — не обычный retry;
- `model_substitution` — несоответствие requested/observed model;
- `gate_schema_error` — ограниченный schema retry;
- `permanent_failure` — halt + `FailureRecord`;
- `committed` — переход уже принят и повторять его нельзя.

Каждая попытка получает `attempt_id`, `retry_index`, `previous_attempt_id`, log digest и typed outcome. Retry policy читает только этот outcome и policy registry. В `engine`, hook и CLI не должно быть трёх независимых счётчиков.

`FAIL`/`BLOCKED` verifier verdict — это evidence о результате работы, а не тот же самый тип, что transport failure. Их нельзя сводить к одному `last_error`.

## Context policy без двойного reread/search stack

Текущий actor-aware ledger — правильная основа и должен стать частью ядра. Его следует расширить через один facade:

```text
ContextPolicy
├── ReadLedger: hash + line intervals + duplicate/partial
├── SearchPolicy: allowlist + graphify exception + plan jump
├── ToolPolicy: role/runtime/tool contract
├── TouchLedger: pre/post write + invalidation + scope
└── TestEvidence: command normalization + fingerprint cache
```

Это не пять независимых hook policies: у них общий `ActorKey`, `ContextDecision`, policy version и один fail-closed boundary. `context_ledger_adapters.py` и `touch_ledger.py` могут временно импортировать facade для старых callers, но не имеют права добавлять новое поведение.

Критерии корректности:

- повторное чтение неизменённого диапазона блокируется;
- изменение файла инвалидирует actors текущей session;
- search вне allowlist разрешён только по typed exception;
- whole-plan read не превращается в скрытый fallback;
- фактический touch scope не подменяется общим `git status`;
- test fingerprint является evidence, а не декоративной telemetry.

## Что остаётся P1/P2, но не должно проникать в ядро

После P0 можно вернуть следующие capability packages:

- incident registry, Tier-1 remediation и runbooks — только поверх `FailureRecord`;
- stack profiles и typed capability execution — только как `CapabilityService` для finish/gate;
- board sync — только как downstream projection с idempotent sync;
- episodes, telemetry, dashboard и sunset — только как read models;
- janitor — только whitelist-only и dry-run;
- DAG/parallel/worktree — отдельный coordinator, выключенный для sequential режима.

Их нельзя использовать как скрытые источники current state, выполнять в hooks «на всякий случай» или возвращать одновременно с упрощёнными аналогами.

## Порядок реализации без наращивания костылей

### Шаг 1. Зафиксировать owner map

Добавить contract test, который утверждает, что только перечисленные владельцы могут:

- менять `LoopState`;
- принимать gate verdict;
- классифицировать session outcome;
- выдавать tool decision;
- публиковать active context.

Проверка imports должна запрещать runtime-вызовы удалённых canonical owners и запись state из `harness/hooks`.

### Шаг 2. Сначала заменить модель состояния и transaction boundary

Расширить текущий cursor до `loop-state/v2`, journal-first commit и typed failure. Не добавлять новые phase branches, пока finish не защищён revision/transaction identity.

### Шаг 3. Перенести phase graph и finish contracts

Перенести из старого phase registry только данные и правила. `engine.py` должен стать тонким фасадом над reducer, а не местом ручного перечисления фаз.

### Шаг 4. Собрать session supervisor

Текущий process streaming переиспользовать как низкоуровневую часть. Вынести из CLI retry/classification в supervisor и сохранять `SessionAttempt` до вызова transition.

### Шаг 5. Объединить boundary и policy

Свести `HookAction`, старый `DecisionEnvelope` и provider outputs к `DecisionEnvelope/v1`. Свести verdict validators и evidence receipt к `ContractRegistry`/`EvidenceService`. Свести context ledger и scope/tool checks к `ContextPolicy`.

### Шаг 6. Только затем вернуть интеграции

Добавлять Claude parity, stack profiles, incidents и projections по одному capability с contract tests. Parallel и board sync не включать в тот же cutover.

## Обязательные доказательства готовности

Новое ядро считается заменившим удалённые системы только если проходят следующие классы tests:

- phase graph: все старые обязательные переходы, включая QA→BUGFIX→QA и DONE guard;
- transaction crash recovery: ни state, ни index не остаются в полусостоянии;
- idempotency: повторный hook/receipt/finish не меняет revision второй раз;
- session taxonomy: timeout, idle, abort, bad model, transient и permanent различаются;
- identity/evidence: stale step, wrong actor, forged receipt и stale fingerprint отклоняются;
- context policy: duplicate, partial, invalidation, search exception, scope и test fingerprint;
- runtime parity: один и тот же canonical decision для Claude и Codex, различается только formatter;
- migration: старый payload/state переводится один раз, после чего old path не пишет;
- owner enforcement: ни один legacy module не участвует в runtime import graph;
- capability isolation: incidents/board/DAG/janitor не могут менять state в обход transition transaction.

Текущие 25 тестов ядра являются smoke/characterization foundation, но не заменяют эти contract tests. Удалённые тесты нужно возвращать не как старую suite целиком, а как отобранные проверки поведения на новые owners.

## Итоговый выбор

Лучший вариант для нового ядра — не «новый engine плюс постепенно возвращаемые старые системы» и не «старый orchestration поверх нового cursor». Это единый domain core с одним state reducer, одним contract registry, одним session supervisor, одной boundary policy и одной transaction boundary.

Старые системы делятся на три группы:

- поведение, которое нужно переписать в новый owner;
- контракты, которые нужно нормализовать и проверить;
- интеграции, которые можно вернуть позже как projections/capabilities.

Нельзя держать одновременно `engine` и `context_loop`, `runtime` и `session_resilience`, текущий `verdict` и старый gate runtime, текущий ledger и старый scope stack. Каждый такой «временный» параллельный путь создаёт два источника истины, после чего следующая заплатка лишь маскирует расхождение.

Критерий готовности прост: на каждую ответственность существует ровно один canonical owner, ровно один wire contract, ровно один путь записи и отдельный test, доказывающий его границу.
