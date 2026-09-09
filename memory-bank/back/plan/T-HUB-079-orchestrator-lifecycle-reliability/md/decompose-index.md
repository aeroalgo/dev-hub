# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-079-orchestrator-lifecycle-reliability
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** 2026-09-09
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (BACK: один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../.cursor/templates/decompose/epic-step.yaml).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | launch returns a stable invocation ID before work; duplicate request with same key returns current/result state and never spawns a second worker. | s01, s02, s06 | |
| FR-002 | only lifecycle owner may transition `created → running → terminal`; parent receives read-only status and cannot mutate markers. | s01, s02, s03, s06 | |
| FR-003 | terminal statuses are exhaustive: `passed`, `failed`, `cancelled`, `stale`, `infrastructure_failure`, `aborted_before_action`; every root prompt reaches one within bounded policy. | s01, s03, s06 | |
| FR-004 | every aborted/dead root session records machine-readable reason, first-action flag, timestamps, owner and retry relation in telemetry/JSONL companion record. | s03, s05, s06 | |
| FR-005 | Todo lifecycle is managed by phase runner: at most start+finish events for IMPLEMENT and explicit diagnostic for third request. | s04, s06 | |
| FR-006 | runtime exposes `await_gate`/`get_invocation_status` with minimum fields; worker prompts do not need filesystem scans of `/tmp`, home or runtime directories. | s02, s04, s05, s06 | |
| AC+ #1 | Eight requests for the same verifier identity yield one execution and the same completed receipt/status. | s01, s02 | |
| AC+ #2 | Crash/TaskStop is terminalized as stale/infrastructure_failure with no parent retry loop or marker deletion. | s03 | |
| AC+ #3 | Empty root session has `aborted_before_action` and a non-empty cause, not an unexplained zero-tool JSONL. | s03, s05 | |
| AC+ #4 | A legitimate new epoch creates a new key; an old result cannot satisfy it. | s01, s02 | |
| AC+ #5 | Third TodoWrite request is rejected/ignored deterministically and becomes telemetry, not a new side effect. | s04 | |
| AC− #1 | No concurrent duplicate verifier/reviewer for equal identity. | s01, s02, s06 | |
| AC− #2 | No runtime-file crawl is presented as supported remediation in agent instructions. | s04, s06 | |
| AC− #3 | No automatic retry after terminal failure without an explicit policy/retry identity. | s03, s06 | |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Stage 1 — lifecycle model and idempotent gate dispatch | plan §Stage 1 | s01, s02 |
| Stage 2 — terminalization and crash safety | plan §Stage 2 | s03 |
| Stage 3 — parent API and Todo policy | plan §Stage 3 | s04 |
| Stage 4 — telemetry migration and purge | plan §Stage 4 | s05, s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единый lifecycle owner и идемпотентное исполнение запусков verifier | s01, s02 |
| Исчерпывающая терминация крахов/TaskStop без дублирования воркеров | s03 |
| Фиксация причин pre-action абортов в телеметрии | s03, s05 |
| Типизированный API статуса ворот без обхода /tmp и runtime файлов | s04, s06 |
| Детерминированное ограничение TodoWrite фазовым раннером | s04 |
| Агрегированные метрики надежности и миграция legacy маркеров | s05 |
| Полная очистка устаревших мутаций, guard-веток и fallbacks | s06 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `ad-hoc in_flight mutation/read branches` | A | `loop.lifecycle.LifecycleReducer` | s06 | no | |
| `scattered duplicate-spawn guards` | A | `loop.lifecycle.create_or_get_invocation` | s06 | no | |
| `implicit root-session retry launcher` | B | `invocation-aware launcher with explicit retry relation` | s06 | no | |
| `retry after TaskStop / empty session silently` | C | `named terminal cause (stale/aborted_before_action) + explicit policy` | s06 | yes | |
| `inspect /tmp/runtime and clear marker advice` | I | `await_gate typed API and operator incident handoff` | s06 | no | |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-lifecycle-state-machine-red-tests.yaml](../yaml/steps/s01-lifecycle-state-machine-red-tests.yaml) | [s01…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s01-lifecycle-state-machine-red-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-idempotent-gate-dispatch.yaml](../yaml/steps/s02-idempotent-gate-dispatch.yaml) | [s02…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s02-idempotent-gate-dispatch.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-terminalization-crash-safety.yaml](../yaml/steps/s03-terminalization-crash-safety.yaml) | [s03…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s03-terminalization-crash-safety.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-typed-parent-api-todowrite-policy.yaml](../yaml/steps/s04-typed-parent-api-todowrite-policy.yaml) | [s04…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s04-typed-parent-api-todowrite-policy.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-telemetry-companion-marker-migration.yaml](../yaml/steps/s05-telemetry-companion-marker-migration.yaml) | [s05…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s05-telemetry-companion-marker-migration.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/implement-T-HUB-079-orchestrator-lifecycle-reliability/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |
