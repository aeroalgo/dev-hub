# Аудит удалённых систем Loop

Дата: 2026-09-18  
Сравнение: `HEAD^` (`974d665`) → `HEAD` (`76397ab`)  
Объект: runtime `loop`, hooks, границы main agent/subagent, retry/resume и контроль контекста.

## Краткий вывод

При cutover было удалено 684 файла: 563 из `loop`, 115 из `harness`, 5 тестовых файлов и 1 runtime-файл Claude. Добавлено 9 файлов и изменено 14. Общий баланс diff: `-146785 / +974` строк.

Главная проблема не в том, что исчезли отдельные утилиты. Была удалена большая часть прежнего orchestration-контракта, а новое ядро пока покрывает только минимальный последовательный цикл:

```text
queue step → IMPLEMENT → AUDIT → QA/BUGFIX/DONE
```

В текущей рабочей директории уже реализованы нативные границы verdict и context в новом ядре, но это ещё не покрывает весь orchestration-контракт. Перед доверием новому Loop необходимо реализовать недостающие P0-сервисы ниже без переноса старых entrypoints и внутренних моделей.

## Методика и критерий «стабильной системы»

Аудит выполнен по трём срезам:

1. статистика удаления `git diff HEAD^ HEAD`;
2. содержимое удалённых canonical-файлов через `git show HEAD^:<path>`;
3. история изменений удалённых владельцев через `git log --follow`.

Под «системой в одном экземпляре» здесь понимается canonical owner конкретной ответственности: один модуль/пакет, на который ссылались остальные части Loop. Это не означает «файл почти не менялся». Например, `loop/context_loop.py` имел 52 исторических изменения, но оставался одним владельцем context-loop semantics; `harness/hooks/epic/core.py` — 54 изменения и один canonical epic hook core.

## Что реально осталось сейчас

| Область | Текущее состояние | Оценка |
|---|---|---|
| Базовый CLI/runtime | `bin/loop.py`, `loop/kernel/cli.py`, `engine.py`, `runtime.py`, `store.py` | Есть минимальный запуск и последовательная обработка очереди |
| Verdict boundary | `loop/kernel/verdict.py`, `lifecycle.py`, `harness/hooks/subagent-start.py`, `subagent-stop.py` | Частично реализовано нативно; есть Pydantic validation, lifecycle receipt и retryable/error классификация |
| Context boundary | `loop/kernel/boundary.py`, `boundary-state.json`, `pretool/posttool-dispatch.py` | Реализовано нативно; есть duplicate-read, partial ranges, actor isolation, edit invalidation, plan guard и scope checks |
| Hook dispatch | `pretool-dispatch.py`, `posttool-dispatch.py`, `stop-gate.py`, `loop_guard.py` | Упрощённая новая цепочка; старый policy stack не возвращён |
| Persistence | `loop/kernel/store.py`, `events.jsonl`, `logs/` | Есть cursor/events/logs, но нет старых checkpoint/episode/finish transaction контрактов |
| Tests | текущий набор kernel/boundary/config/scope tests | 26 тестов проходят, но 348 старых Loop-тестов и 108 hook-тестов удалены |
| Runtime registration | `.codex/hooks.json` ссылается на новые hooks | Codex-путь подключён; текущий `.claude/settings.json` содержит только permissions и не заменяет удалённую регистрацию `.claude/hooks` |

## Критические удалённые системы

### P0 — нужно реализовать до эксплуатационного запуска

| Canonical owner в `HEAD^` | Что он обеспечивал | Что есть сейчас | Риск | Рекомендация |
|---|---|---|---|---|
| `loop/context_loop.py`, `loop/epic_transition.py`, `loop/roadmap_queue.py`, `loop/phase_registry.yaml` | Полную state machine фаз, `activeContext`, decompose index, ANALYZE/CREATIVE gates, roadmap cadence, no-neighbor-carry, QA-pass-required DONE | `loop/kernel/engine.py` знает только минимальные переходы IMPLEMENT/AUDIT/QA/BUGFIX/DONE | Шаг может завершиться формально, пропустить старую фазовую политику или перейти с неполным контекстом | Реализовать native phase/transition service и сделать его единственным владельцем переходов |
| `loop/schemas/*` | Строгие контракты active context, checkpoint, boundary registry, decompose index, episode, handoff, gate verdict, QA outcome, state, telemetry и repair result | Несколько dataclass + Pydantic-модели verdict/repair result | JSON/YAML может пройти границу с неполной структурой; hooks не смогут надёжно различать валидный verdict, checkpoint и handoff | Реализовать native schema registry; verdict, transition, checkpoint, handoff и finish result должны валидироваться до атомарных действий |
| `loop/runner/session.py`, `runner/orchestrator.py`, `runner/ownership.py`, `runner/config.py`, `runner/output.py` | Реальный session lifecycle: structured outcomes, abort taxonomy, stream/tool errors, timeout/idle detection, retry/backoff, model substitution detection, dirty-path filtering, finish integrity, checkpoint trace | `loop/kernel/runtime.py` запускает subprocess и возвращает базовый result; retry в engine ограничен попыткой шага и `last_error` | Обрыв связи, зависание, неверный runtime output или подмена модели могут быть ошибочно приняты за обычную ошибку; контекст прошлого результата не имеет нового session contract | Реализовать native session outcome/attempt record, классификатор transient/permanent, bounded retry с контекстом предыдущего результата и persisted recovery state |
| `harness/hooks/session_resilience.py` | Hook-level recovery, retry, timeout/crash handling и защита от бесконечных повторов | Новые hooks не содержат эквивалентного resilience слоя | Loop может потерять шаг между subprocess и hook boundary | Сделать resilience частью общей lifecycle state machine, а не отдельным неструктурированным fallback |
| `harness/hooks/_lib.py`, `harness/hooks/epic/core.py`, `hook_dispatch.py`, `gate_runtime.py`, `gate_receipt.py` | Общий typed event/decision boundary, нормализация hook input/output, canonical epic state/layout, receipts для завершения gate | `BoundaryService`, verdict/lifecycle и минимальные hook functions | Хуки могут видеть разные формы события; атомарное завершение шага не гарантируется одинаково для Codex/Claude | Реализовать единый native `DecisionEnvelope`/event envelope и один dispatcher для всех runtime hooks |
| `harness/hooks/context_scope.py`, `context-scope-pretool.py`, `pretool_policy.py`, `agent_policy.py` | Search allowlist, graphify exception, test fingerprint cache, whole-plan policy, agent-specific tool policy | `BoundaryService` защищает чтение файлов и touched scope, но не весь search/tool policy | Агент может перечитывать план, искать за пределами scope или использовать инструмент вне своей роли | Расширить новый boundary contract до полного read/search/tool policy; отдельные правила не прятать в prompt |
| `harness/hooks/stop-gate.py`, `subagent-stop.py` старого поколения | Финальная проверка evidence/fingerprint, demotion, gate closure и rich subagent lifecycle | Новые версии проверяют только урезанный verdict/lifecycle contract | STOP или subagent completion может быть принят без полного evidence bundle | Реализовать native stop decision envelope, fingerprint/evidence checks и обязательную atomic finalization |
| `loop/mb_load/*`, `loop/mb_finish/*`, `loop/mb_scaffold/*` | Typed загрузку Memory Bank, session context, plan-jump policy, scaffold-only generation, finish transaction, verify hints и atomic finish/index state | `loop/kernel/index.py` читает простой YAML `steps` и меняет status | Dirty tree не даёт надёжного результата шага; finish может быть неатомарным, а следующий агент — получить неполный контекст | Реализовать новый load/finish service вокруг boundary, verdict и cursor; scaffold и finish должны иметь отдельные схемы |

### P1 — критично для надёжности и управляемого восстановления

| Canonical owner в `HEAD^` | Что было удалено | Риск сейчас | Рекомендация |
|---|---|---|---|
| `loop/incidents/*`, `loop/incidents/tier1_runner.py`, `loop/incidents/runbooks/*` | Incident schema/registry/events/trace/metrics/store, Tier-0/Tier-1 eligibility, attempts, scope, verify, escalation и runbooks | Ошибка остаётся `last_error`; нет durable incident, эскалации, bounded remediation и audit trail | Реализовать incident record + registry + typed escalation после исчерпания retry |
| `loop/janitor/gc.py`, `loop/janitor/*` | Whitelist-only bounded repair, `GcResult`, dry-run и безопасное удаление только разрешённых runtime/episode/event paths | Нет контролируемого cleanup; возможны orphaned state/logs или ручное опасное удаление | Реализовать janitor только после schema/incident layer, с whitelist и dry-run по умолчанию |
| `loop/runtime_adapters/*`, `runtime_materializers/*`, `runtime_registry.yaml` | Provider-neutral Claude/Codex/DSH adapters, agent contract, collaboration adapter, subagent lifecycle, hook JSON materializer, manifest/parity checks, policy mapping и fingerprint checks | Есть выбор executable, но нет полного parity/contract enforcement между runtime | Реализовать adapter contract и materialization/parity checks; отдельно проверить Claude registration |
| `loop/runtime_adapters/agent_contract.py` | Универсальный contract для agent outputs, JSON fences, `GATE_IDENTITY`, verify/explorer/sunset/gate-repair/reconcile policies | Новый verdict schema не заменяет инструкции и policy для разных agent roles | Реализовать role contract поверх единого envelope, чтобы role policy проверялась до spawn и после stop |
| `loop/stack_profiles/*` | Capability profile registry/resolver, typed execution evidence и doctor | Правила проекта из `AGENTS.md` требуют stack profiles, но kernel их не исполняет | Реализовать capability checks и typed execution evidence; FRONT/BACK не должны сводиться к одному generic command |
| `loop/board_launch/*`, `loop/board_sync/*` | Arm/run metadata, scan MB/gates, card model, diff, sync, resolver, client/host/workspace и board status | Loop может локально завершить работу без синхронизации внешнего статуса | Реализовать после P0; сначала read-only scan/diff, затем atomic sync |
| `loop/workflow/*`, `workflow_pack_registry.yaml`, `loop/formulas/*`, `loop/paths/*` | Workflow pack graph/registry, intent routing, skill refs, tool gates, formula contracts и canonical paths | Локальные `AGENTS.md`/Cursor rules есть, но runtime не имеет прежнего workflow registry | Реализовать registry/intent routing или явно зафиксировать новый минимальный контракт в схемах |
| `loop/dag.py`, `loop/parallel/*` | Dependency DAG, ready waves, overlap detection, worktrees, status flock, max parallel и recursive disable | Сейчас очередь последовательная; параллелизм не поддержан, а совместимость с DAG потеряна | Не включать parallel до реализации native overlap/worktree/status contracts; затем добавить как отдельный режим |

### P2 — observability, audit и долговременная эксплуатация

| Canonical owner в `HEAD^` | Что было удалено | Что теряется |
|---|---|---|
| `loop/episodes/*`, `loop/session_finalize.py`, `loop/telemetry.py`, `loop/dashboard/*` | Episode bundle, retention, dashboard schema/collect/render, telemetry и session finalization | Нельзя полно реконструировать, что произошло на границе шага, какие verdicts были приняты и почему |
| `loop/sunset_sidecar_store.py`, sunset schemas | Durable sunset/retirement sidecar state | Состояние вывода/закрытия задач может жить только в текущем дереве |
| `loop/qa_*`, `loop/roadmap_*`, `loop/bugfix_queue.py`, `loop/analyze_gate.py`, `loop/decompose_gate.py`, `loop/halt_logic.py`, `loop/git_discipline.py` | Специализированные gates, roadmap, bugfix queue, halt и git discipline policies | Упрощённая engine transition не заменяет отдельные причины остановки и критерии готовности |

## Системы, которые были особенно стабильными по истории

Это не автоматическое доказательство корректности, но хороший сигнал, какие owners нельзя было удалять без characterization tests:

| Owner | Исторических ревизий до cutover | Почему важен |
|---|---:|---|
| `harness/hooks/epic/core.py` | 54 | Canonical state/layout/epic hook core |
| `loop/context_loop.py` | 52 | Canonical context-loop и фазовая семантика |
| `harness/hooks/_lib.py` | 40 | Общая hook-инфраструктура и shared primitives |
| `harness/hooks/session_resilience.py` | 30 | Crash/timeout/retry/recovery contract |
| `loop/epic_transition.py` | 26 | Переходы между фазами и completion policy |
| `harness/hooks/subagent-stop.py` | 26 | Граница завершения subagent |
| `harness/hooks/stop-gate.py` | 24 | Финальная граница остановки Loop |
| `loop/runtime_adapters/subagent_lifecycle.py` | 12 | Provider/runtime-neutral lifecycle |
| `loop/mb_load/session.py` | 7 | Context loading и session boundary |
| `loop/runner/orchestrator.py` | 5 | Canonical Loop orchestration |
| `loop/janitor/gc.py` | 5 | Бounded cleanup и repair |
| `loop/board_sync/sync.py` | 5 | Board synchronization |

Особенно заметно, что `context_loop.py`, `epic/core.py`, `_lib.py` и resilience/stop hooks были не случайными экспериментами: они были многократно дорабатываемыми canonical owners. Их отсутствие нельзя компенсировать тем, что новый `engine.py` запускается и несколько smoke-тестов проходят.

## Что уже реализовано в новом ядре, но пока не закрывает весь смысл операции

### Verdict boundary

В новом ядре реализованы `Pydantic`-валидация verdict и repair result, lifecycle receipts и hook interception через `subagent-start/stop`. Это закрывает базовую границу `subagent → hook`, но пока не закрывает:

- полный schema registry для checkpoint/handoff/finish/transition;
- старую role-specific agent policy;
- evidence/fingerprint-проверки старого stop gate;
- persisted session outcome и incident escalation;
- одинаковую регистрацию и поведение для Claude и Codex.

### Context boundary

В новом `BoundaryService` реализованы duplicate-read/hash-aware semantics, partial ranges, actor isolation, edit invalidation, ограничение чтения плана и touched scope в одном `boundary-state.json`. Это правильный фундамент для защиты от reread и dirty-tree drift, но пока отсутствуют search/tool policy, test fingerprint cache, полный plan-jump contract и finish transaction.

Иными словами: текущая реализация переносит инварианты операций в новый контракт, а не восстанавливает старую структуру. Она пока не доказывает, что все прежние операции покрыты.

## Рекомендуемый порядок нативной реализации

1. **P0. Contract layer:** schema registry для verdict, transition, checkpoint, handoff, finish и session outcome.
2. **P0. State machine:** реализовать native phase transition, active context/decompose semantics, ANALYZE/CREATIVE/QA gates и atomic finish.
3. **P0. Session resilience:** persisted attempts, transient/permanent classification, timeout/idle/crash handling, bounded retry и передача предыдущего результата в следующий prompt.
4. **P0. Hook parity:** единый dispatcher/envelope, native scope/tool policies, stop gate и lifecycle; проверить регистрацию Claude отдельно от Codex.
5. **P0. Contract tests:** написать characterization/contract tests для этих четырёх границ до дальнейшей оптимизации.
6. **P1. Recovery:** incidents, Tier-1 runner, janitor и runbooks как новые сервисы.
7. **P1. Runtime/project integration:** adapters/materializers, agent contracts, stack profiles и capability checks в модели нового runtime.
8. **P1/P2. External state и observability:** board sync, episodes, telemetry, dashboard, sunset sidecar.
9. **P2. Parallel mode:** DAG/overlap/worktree только после стабилизации native sequential contracts и отдельного набора safety tests.

## Итоговый список того, что, вероятнее всего, забыли учесть

- [ ] Полную native phase/transition state machine вместо минимального `engine.py`.
- [ ] Schema registry для всех межагентных и межфазовых payloads, не только verdict.
- [ ] Реальный session runner: abort taxonomy, timeout/idle, retry/backoff, model substitution и checkpoint.
- [ ] `session_resilience` как часть lifecycle, а не только retry счётчик в cursor.
- [ ] Shared hook dispatcher и typed decision/event envelope.
- [ ] Search/tool/agent policy и test fingerprint cache поверх `BoundaryService`.
- [ ] Полный stop gate с evidence/fingerprint и atomic finish.
- [ ] MB load/finish/scaffold contracts.
- [ ] Incident registry, Tier-1 runner, escalation и whitelist janitor.
- [ ] Provider parity/materializers и role-specific agent contracts.
- [ ] Claude hook registration/parity; сейчас явно подтверждён только Codex config.
- [ ] Stack profiles и typed capability execution evidence.
- [ ] Удалённый characterization test suite: 456 файлов тестов/fixtures в старых подсистемах не должен исчезать без замены контрактными тестами.
- [ ] Episodes/telemetry/dashboard/session finalization для расследования boundary failures.

## Ограничения аудита

Этот документ не утверждает, что каждая из 684 удалённых единиц должна быть возвращена буквально. Часть старых файлов должна быть заменена более простым дизайном. Но для каждой операции должна существовать явная новая точка владения, схема, тест и receipt на границе. На текущем срезе такая native-реализация явно прослеживается для базового runtime, verdict/repair validation и context boundary; для остальных систем это пока gap, а не подтверждённая миграция.
