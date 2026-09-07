# T-HUB-079 — Надёжный lifecycle сессий, сабагентов и terminal telemetry

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear. **Prompt:** [md/prompt.md](prompt.md)

## Контекст и цель

В последних 20 root sessions семь `BACK DECOMPOSE` остановились до первого action, один был частично начат. В активных flow verifier запускался многократно после `TaskStop`, а TodoWrite превышал лимит. Эти события не должны превращаться в новую независимую сессию, duplicate subagent или ручную state repair.

Цель: для каждого `(session, phase, step, gate role)` существует один lifecycle owner и идемпотентный результат. Любая остановка получает terminal event с причиной, доступной оператору и audit без чтения runtime файлов агентом.

## Product probe

| Probe | Решение |
|---|---|
| Реальная проблема | Потерянные/дублированные invocation делают workflow непредсказуемым и провоцируют обход gate. |
| Wedge | Durable lifecycle state machine, idempotency keys и typed status API. |
| Pre-mortem | Простое mutex-lock решение зависнет после crash. Нужны lease, owner identity и explicit stale transition. |
| Leverage | Existing spawn-gate state, stop hooks, telemetry and session JSONL become inputs to one reducer. |
| Appetite | 3 дня; не менять provider-specific subagent implementation. |

## Requirements

- **FR-001:** launch returns a stable invocation ID before work; duplicate request with same key returns current/result state and never spawns a second worker.
- **FR-002:** only lifecycle owner may transition `created → running → terminal`; parent receives read-only status and cannot mutate markers.
- **FR-003:** terminal statuses are exhaustive: `passed`, `failed`, `cancelled`, `stale`, `infrastructure_failure`, `aborted_before_action`; every root prompt reaches one within bounded policy.
- **FR-004:** every aborted/dead root session records machine-readable reason, first-action flag, timestamps, owner and retry relation in telemetry/JSONL companion record.
- **FR-005:** Todo lifecycle is managed by phase runner: at most start+finish events for IMPLEMENT and explicit diagnostic for third request.
- **FR-006:** runtime exposes `await_gate`/`get_invocation_status` with minimum fields; worker prompts do not need filesystem scans of `/tmp`, home or runtime directories.

## AC

1. Eight requests for the same verifier identity yield one execution and the same completed receipt/status.
2. Crash/TaskStop is terminalized as stale/infrastructure_failure with no parent retry loop or marker deletion.
3. Empty root session has `aborted_before_action` and a non-empty cause, not an unexplained zero-tool JSONL.
4. A legitimate new epoch creates a new key; an old result cannot satisfy it.
5. Third TodoWrite request is rejected/ignored deterministically and becomes telemetry, not a new side effect.

### AC−

- No concurrent duplicate verifier/reviewer for equal identity.
- No runtime-file crawl is presented as supported remediation in agent instructions.
- No automatic retry after terminal failure without an explicit policy/retry identity.

## Technology axiom

| Choice | Input | Forbidden |
|---|---|---|
| durable reducer state machine | immutable invocation events | direct marker edits as transitions |
| idempotency key | session + phase + step + role + epoch | name-only duplicate detection |
| typed read-only status | invocation ID | parent filesystem inspection |
| terminal telemetry record | every root invocation | silent zero-action abort |

## Architecture

```text
runner prompt -> create_invocation(key) -> owner lease -> subagent
                                 | duplicate -> current status/receipt
subagent stop/crash -> reducer terminal event -> telemetry + gate receipt
parent -> await_gate(invocation_id) -> typed status only
```

The reducer owns persistence and cleanup. A stale lease is resolved by reducer policy, never by a parent-side JSON rewrite. T-HUB-077 provides trusted receipt semantics; this epic consumes it and owns only dispatch/lifecycle reliability.

## Failure matrix

| Failure | Detection | Response | Test |
|---|---|---|---|
| duplicate spawn | idempotency key hit | return same invocation | TM-079-01 |
| process crash | lease expiry/no stop event | stale terminal event | TM-079-02 |
| prompt dies before action | launcher callback missing | aborted_before_action record | TM-079-03 |
| old epoch retry | key/epoch mismatch | reject/rearm explicitly | TM-079-04 |
| third Todo request | lifecycle counter | deny/no-op telemetry | TM-079-05 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| ad-hoc `in_flight` mutation/read branches | reducer transitions | delete in-epic |
| scattered duplicate-spawn guards | single idempotency resolver | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| implicit root-session retry launcher | invocation-aware launcher | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| retry after TaskStop / empty session silently | named terminal cause + explicit retry | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| inspect `/tmp`/runtime and clear marker advice | `await_gate` status and operator incident handoff | delete in-epic |

## Stages

### Stage 1 — lifecycle model and idempotent gate dispatch

- Specify event/state schema, idempotency key and legal transitions; persist before spawning.
- Convert verifier/reviewer launch to `create_or_get_invocation` and add concurrency tests for repeated calls.
- Ensure receipt links to invocation ID and epoch; consume trusted receipt contract from T-HUB-077.

### Stage 2 — terminalization and crash safety

- Add lease/heartbeat and reducer-owned stale detection; preserve forensic event sequence.
- Record `first_action_at` and terminal cause for every root invocation, including pre-action abort.
- Add tests for TaskStop, crash after reservation, lock contention and stale recovery without duplicate work.

### Stage 3 — parent API and Todo policy

- Replace raw runtime discovery in prompt-building with typed status API and concise remediation classes.
- Centralize Todo start/finish ownership and reject third action without changing user task state.
- Update agent instructions to remove runtime crawl/repair language and retain fail-closed next action.

### Stage 4 — telemetry migration and purge

- Add compatibility migration that turns existing marker-only records into `legacy_unknown` diagnostics, never PASSED.
- Emit aggregate counters: duplicate-suppressed, terminal-by-cause, zero-action sessions and retry chains.
- Remove obsolete manual retry/marker-clear code and prove remaining instruction surfaces contain only typed APIs.

## QA consumes

| ID | Priority | Scenario | Expected | Maps |
|---|---|---|---|---|
| TM-079-01 | P0 | concurrent duplicate verifier launch | one owner, one receipt | FR-001 |
| TM-079-02 | P0 | TaskStop/stale lease | terminal failure, no re-spawn | FR-002/3 |
| TM-079-03 | P0 | no first tool action | terminal abort record | FR-004 |
| TM-079-04 | P0 | retry in new epoch | old result rejected | FR-001/2 |
| TM-079-05 | P1 | three TodoWrite attempts | only two transitions | FR-005 |
| TM-079-06 | P1 | parent status lookup | no runtime traversal required | FR-006 |

## Review readiness

Product probe, delivery closure, engineering spine, QA matrix and review batch are done. Dependency on T-HUB-077 is explicit; no critical ambiguity remains.

## Appetite and next mode

`timebox_days: 3`; cut first: dashboard visualisation and cross-provider shared leases.  
→ **BACK DECOMPOSE T-HUB-079-orchestrator-lifecycle-reliability**
