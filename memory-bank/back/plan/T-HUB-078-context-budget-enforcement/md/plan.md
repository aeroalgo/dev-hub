# T-HUB-078 — Универсальный ledger чтения и исполнимый бюджет контекста

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear. **Prompt:** [md/prompt.md](prompt.md)

## Контекст и цель

Аудит обнаружил 500 Read в 12 активных сессиях, включая 105 повторных Read одного файла, 25/19 Read двух других файлов и повторную загрузку полного `plan.md` в lean IMPLEMENT. Текстовые правила уже запрещают это, но runner и tool boundary не измеряют и не блокируют нарушение.

Цель: любой агент — root-agent или subagent — получает минимальный, воспроизводимый контекст и не может бесконтрольно reread, загрузить monolithic plan или выполнить поиск за file allowlist без явного graphify-backed исключения. Один и тот же policy/ledger должен работать для Claude Code и Codex; provider-specific hook/adapter является только транспортным входом, а не отдельной реализацией правила.

## Универсальный runtime contract

### Scope владельца ledger

Ledger scoped не на имя процесса и не на тип модели, а на устойчивую цепочку:

```text
(project_root, root_session_id, agent_invocation_id, runtime_provider)
```

`agent_invocation_id` для root-agent равен root session identity; для subagent берётся из события запуска/остановки и связывается с parent invocation. Если provider не передаёт отдельный invocation id, adapter обязан сгенерировать детерминированный fallback из session id + tool-use id + launch sequence и записать это как `derived_identity`, а не молча смешать все чтения в один глобальный bucket.

Одна сессия может иметь общий project-level ledger, но записи root-agent и каждого subagent должны оставаться различимыми. Это позволяет запретить повторное чтение внутри конкретного исполнителя и одновременно не считать чтение parent автоматически прочитанным child или наоборот.

### Provider parity matrix

| Область | Claude Code | Codex | Единый контракт |
|---|---|---|---|
| Root-agent read | `PreToolUse`/tool payload из Claude settings | Codex hook/event bridge или wrapper payload | `ReadRequest` → `ContextLedger.decide()` |
| Subagent read | `SubagentStart` + дочерний tool stream | materialized agent policy + Codex event stream | invocation lineage сохраняется; policy не ослабляется |
| Edit/Write invalidation | `Write|Edit|NotebookEdit` pre/post boundary | соответствующий Codex write event/bridge | новая content version инвалидирует записи файла |
| Deny/diagnostic | Claude `permissionDecision=deny` + `additionalContext` | Codex hook non-zero/structured diagnostic | один `DecisionReceipt` schema и одинаковые reason codes |
| Finish metrics | Stop/SubagentStop/session telemetry | Codex stream/session telemetry | одинаковые counters без содержимого файлов |

Claude и Codex могут различаться только форматом входного/выходного события. Нельзя иметь отдельный `if claude` и `if codex` с разными правилами duplicate detection.

### Read semantics

Каждая запись хранит не содержимое файла, а metadata:

```text
ReadRecord {
  canonical_path,
  content_hash,
  line_interval,
  mode,
  purpose,
  actor_kind,          # root | subagent
  runtime_provider,    # claude | codex | other adapter
  session_id,
  invocation_id,
  sequence,
  decision,
}
```

Правила интервалов:

1. точное пересечение неизменённого диапазона → `duplicate` и deny/cache-reference;
2. частичное пересечение → разрешить только непокрытый интервал и записать split decision;
3. диапазоны без пересечения → разрешить и объединить в interval set;
4. полный файл считается диапазоном `1..EOF` только если инструмент действительно вернул полный файл;
5. отсутствие диапазона не даёт права считать прочитанным весь файл — запрос нормализуется по фактическому ответу или получает conservative deny;
6. `Read` другого actor не закрывает диапазон текущего actor;
7. повтор после изменения содержимого получает новую `content_hash` и начинает новый набор интервалов.

### Edit invalidation

После успешного изменения файла ledger обязан перейти на новую content version до следующего `Read`. Минимальный безопасный контракт — удалить все ranges конкретного `canonical_path`; оптимизация может сохранить непересекающиеся ranges только если edit event содержит проверенный old/new diff и новую hash. Любой `Write`, `Edit`, `NotebookEdit`, atomic replace, rename и внешнее изменение должен приводить к re-stat/hash check перед выдачей решения.

`mtime` разрешён только как быстрый cache hint. Истиной является content hash; если hash недоступен, решение fail-closed с причиной `content_version_unknown`, а не silent cache hit.

## Product probe

| Probe | Решение |
|---|---|
| Реальная проблема | Дорогой контекст скрывает scope drift и делает поведение агента непредсказуемым. |
| Wedge | Read ledger + plan-jump projection + search allowlist в одном session contract. |
| Pre-mortem | Жёсткий лимит сломает легитимный debug. Поэтому исключения должны быть typed, reasoned и наблюдаемы. |
| Leverage | Existing shard `files`, `plan_jumps`, graphify и pretool hooks уже являются нужными входами. |
| Appetite | 3 дня; не строить general LLM token meter. |

## Requirements

- **FR-001:** session ledger хранит canonical realpath, content hash/version, range, purpose и sequence Read; повтор полного неизменённого Read получает denial/cached reference.
- **FR-002:** после Edit допускается только diff или declared symbol/range; новый full Read требует explicit exception reason.
- **FR-003:** PLAN runner materializes `plan_jumps` into bounded excerpts; IMPLEMENT Read whole `md/plan.md` denied unless plan-mode/approved exception.
- **FR-004:** search command derives allowlist from shard `files`, declared delta and parent dirs. Выход за неё требует successful graphify query plus typed reason.
- **FR-005:** end-of-session telemetry reports `unique_reads`, `duplicate_reads`, bytes/ranges, monolith-plan attempts, search exceptions and highest-repeat path.
- **FR-006:** targeted test command results are fingerprinted by command + relevant diff; exact repeat without changed inputs returns cached result or explicit no-op record.
- **FR-007:** один и тот же ledger policy применяется к root-agent и каждому subagent в Claude Code и Codex; различия provider payload не меняют duplicate/read-after-edit semantics.
- **FR-008:** ledger scope различает `(project, root session, actor invocation)` и не переносит факт чтения между parent/child автоматически.
- **FR-009:** после успешного изменения или обнаружения внешнего изменения файла прежние ranges этого файла недействительны до подтверждения новой content hash.
- **FR-010:** повторный полный/частичный Read возвращает machine-readable decision receipt с `allowed|duplicate|partial|invalidated|denied|exception`, reason code и canonical path, но никогда не включает содержимое файла.

## AC

1. Repeating the same full Read in IMPLEMENT is blocked/cached, increments `duplicate_reads`, and cannot produce a second full context payload.
2. A plan jump succeeds while whole plan Read is denied in IMPLEMENT.
3. Search inside shard paths works; search outside requires graphify evidence and records its reason.
4. A real code edit permits a narrow post-edit diff read, not silent stale caching.
5. Telemetry distinguishes allowed reads, denied rereads and approved exceptions without storing secret file content.
6. Root-agent and two subagents reading the same unchanged range receive independent, deterministic decisions in both Claude and Codex fixtures.
7. A write by root-agent invalidates the same file for root-agent and subagents; each actor may read the new version once, then duplicate protection applies again.
8. Provider event aliases (`Read`/`read`, `Edit`/`Write` and equivalent Codex payloads) converge to the same normalized request and decision.

### AC−

- No hidden global bypass for `Read`, `rg`, `cat`, Python file reads or wrapper aliases.
- No failure mode that silently falls back to full plan/read-all-memory-bank.
- No test cache reuses a command after relevant files changed.
- No process-local-only ledger that disappears between hook invocations.
- No provider-specific bypass through child agents, aliases, wrapper commands or a second hook registration.

## Technology axiom

| Выбор | Input | FORBIDDEN |
|---|---|---|
| session-scoped typed ledger | canonical path + hash + range | transcript-only memory / untracked reread |
| bounded context projection | shard `plan_jumps`, files and delta | full plan as default AC |
| policy decision receipt | graphify result + reason | broad rg by convenience |
| deterministic test fingerprint | normalized command + diff fingerprint | cache hit on changed input |

## Architecture

```text
Prompt projection -> shard/files/plan_jumps
Tool preflight -> ContextLedger -> allow | cached-ref | deny | exception receipt
Search preflight -> ScopeResolver -> local allowlist | graphify-backed exception
Finish telemetry -> session metrics -> handoff/audit artifact
```

Ledger is an enforcement service used by the tool wrappers, not prose parsed from agent messages. It records metadata only; content remains in normal tool results. ScopeResolver is pure/testable and receives no agent-authored wildcard as authority. The persistence boundary must be shared by short-lived Claude hook processes, Codex hook processes and subagent processes; an in-memory set is only an optimization layer and cannot be the source of truth.

### Proposed module boundaries

The implementer must preserve these responsibilities even if existing paths differ during DECOMPOSE:

| Boundary | Responsibility | Required tests |
|---|---|---|
| `harness`/`loop` shared ledger module | canonical path, hash/version, interval algebra, actor/session key, decision receipt | pure unit tests with no provider |
| Claude hook adapter | parse Claude Read/Edit payloads and map decision to permission response | hook fixtures |
| Codex runtime adapter/bridge | parse Codex event aliases and map same receipt to exit/structured output | Codex bridge fixtures |
| session state/telemetry adapter | durable atomic persistence, lock/concurrency, counters and finish projection | persistence/concurrency tests |
| policy/instruction materializer | inject concise shared rule into root and subagent contracts | parity/contract tests |

The exact module paths are to be confirmed in DECOMPOSE from the current hook registry. A new parallel hook entrypoint is forbidden; existing registration must route to the shared policy boundary.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Duplicate/read-after-edit protection | `vertical_slice` | Claude `PreToolUse` and Codex event bridge → shared ledger decision → provider response | duplicate is denied/cached; changed version is re-read only under new hash; unknown version fails closed | equivalent root/subagent Claude/Codex fixtures prove same receipt and no second payload | `n/a` |
| Plan-jump and search scope | `vertical_slice` | session prompt/context projection → Read/search preflight | whole plan/out-of-scope search denied unless typed exception receipt | IMPLEMENT fixture accepts jump and rejects whole plan | `n/a` |
| Read telemetry | `vertical_slice` | session finish/telemetry projection → machine counters | missing or corrupt ledger cannot produce green finish metrics | finish fixture validates counters and secret-free metadata | `n/a` |

## Eng review spine

### Data flow

```text
Claude/Codex tool event
  -> provider adapter
  -> normalized ReadRequest / EditEvent
  -> durable ContextLedger (hash + interval set + actor key)
  -> DecisionReceipt
  -> provider deny/allow response + finish telemetry
```

The provider adapters are transport-only. The pure normalizer and decision service are the single policy boundary. Persistence is atomic and session-scoped; concurrent hook processes must serialize updates for the same ledger key.

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|---|---|---|---|---|
| path normalizer | symlink/relative alias | canonical path differs from raw input | resolve within project root or deny | TM-078-01 |
| content version | hash unavailable or changed during read | pre/post hash mismatch | fail closed; require fresh read/exception | TM-078-02/TM-078-09 |
| interval algebra | full/partial range overlap | interval set intersection | deny duplicate or return missing subrange only | TM-078-01/TM-078-11 |
| persistence | hook process restart | ledger record absent/invalid | deny rather than allow silent reread; diagnostic is recoverable | TM-078-10 |
| concurrency | root and child update same path | lock/version conflict | retry bounded atomic operation or deny with receipt | TM-078-07 |
| provider adapter | Claude/Codex payload mismatch | normalized request fixture divergence | fail parity check; no provider-local fallback | TM-078-08 |
| write boundary | edit event not observed | next hash differs from stored version | invalidate all old ranges before decision | TM-078-09 |
| finish projection | telemetry write fails | schema/atomic write error | non-green diagnostic; never claim zero duplicates | TM-078-06 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|---|---:|---|
| Data flow complete | 5 | Provider input, shared decision, persistence and finish output are explicit. |
| Failure coverage | 5 | Hash, ranges, aliases, concurrency, restart and provider parity are covered. |
| Testability | 5 | Pure policy tests are separated from Claude/Codex adapter and hook integration fixtures. |

## Failure matrix

| Failure | Detection | Response | Test |
|---|---|---|---|
| same path/hash full Read | ledger key hit | cached/deny | TM-078-01 |
| changed file reread | hash mismatch | permit diff range | TM-078-02 |
| whole plan in IMPLEMENT | mode/path policy | deny + suggest jump | TM-078-03 |
| rg outside shard | allowlist miss | require graphify receipt | TM-078-04 |
| same test after edit | diff fingerprint differs | execute, no cache | TM-078-05 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| untracked Read/tool usage | ContextLedger preflight | delete in-epic |
| ad-hoc context counting | typed metrics producer | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| raw runner injection of plan path | generated jump excerpt | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| policy failure → broad read/search | explicit deny or exception receipt | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| prose-only reread/graphify guidance | runner-enforced contract + concise diagnostic | delete in-epic |

## Stages

### Stage 1 — ledger and read policy

- Define serialized `ContextReadRecord`, `DecisionReceipt`, actor/session key and pure decision function with modes PLAN/IMPLEMENT/TASK/BUGFIX/QA.
- Implement canonical path, content hash and closed/open interval algebra; cover EOF, omitted range, overlapping ranges and path aliases.
- Add durable atomic ledger storage with per-session/invocation lock; preserve only metadata and counters, never source content.
- Write Red tests for repeat full Read, partial overlap, post-edit narrow Read, path-alias bypass, parent/child isolation and cross-process persistence; implement minimal green behavior.

### Stage 2 — plan-jump projection and monolith guard

- Parse shard `plan_contract.plan_jumps`, materialize exact permitted excerpts and attach their identity to prompt/session state.
- Reject whole plan paths in lean code modes with a diagnostic naming the valid jump.
- Preserve full plan access for PLAN/DECOMPOSE/ANALYZE/AUDIT, where it is legitimate.
- Ensure the same mode decision is injected into root-agent and subagent context contracts; a subagent cannot regain whole-plan access by using a provider-specific entrypoint.

### Stage 3 — search and test execution contracts

- Build ScopeResolver from shard files/delta/parent dirs; support graphify receipt validation for expanded search.
- Fingerprint test execution by normalized command and relevant changed paths; emit cache/no-op evidence instead of hiding repeats.
- Add policy tests covering `rg`, tool aliases and Python-wrapper read/search invocations that bypass simple string matching.
- Add Claude and Codex adapter fixtures for equivalent Read/Edit/Write payloads, including lowercase aliases and missing-range payloads; assert identical normalized receipts.
- Wire invalidation at every supported write boundary and test root edit → subagent read, subagent edit → root read, rename/delete and external mutation detection.

### Stage 4 — metrics, migration and purge

- Expose finish-safe metrics in handoff/diagnostic output; establish budgets as warnings first, then enforce after baseline.
- Remove duplicate context-counting/prompt prose that conflicts with ledger decisions.
- Regression-test a real shard flow: one allowed code map, one TDD cycle, no monolithic plan and no duplicate full Read.
- Materialize the shared contract into Claude root/subagent instructions and Codex agent/policy artifacts; run parity checker against generated surfaces.
- Remove any provider-local duplicate-read counters or prose-only enforcement that can disagree with the shared receipt; keep one documented exception path with reason code.

## QA consumes

| ID | Priority | Scenario | Expected | Maps |
|---|---|---|---|---|
| TM-078-01 | P0 | same full path/range/hash twice | deny/cache, metric increments | FR-001 |
| TM-078-02 | P0 | file changed then narrow read | allowed with diff evidence | FR-002 |
| TM-078-03 | P0 | IMPLEMENT whole plan vs jump | plan denied, jump allowed | FR-003 |
| TM-078-04 | P0 | search beyond files | deny until graphify receipt | FR-004 |
| TM-078-05 | P1 | repeated test then changed diff | cache then rerun | FR-006 |
| TM-078-06 | P1 | finish telemetry | exact aggregate fields | FR-005 |
| TM-078-07 | P0 | root + two subagents read same range | actor-isolated deterministic decisions | FR-007/8 |
| TM-078-08 | P0 | Claude/Codex equivalent payloads | same normalized receipt/reason code | FR-007/10 |
| TM-078-09 | P0 | root edit then child read | old ranges invalidated; new version allowed once | FR-009 |
| TM-078-10 | P1 | hook process restart | durable ledger preserves duplicate decision | FR-008 |
| TM-078-11 | P1 | aliases and omitted ranges | no bypass; conservative normalization | FR-010 |

## Review readiness

All required rows are done: Product probe, data flow/failure matrix, delivery closure, QA matrix and plan review. No unresolved CRITICAL ambiguity.

## Appetite and next mode

`timebox_days: 3`; cut first: adaptive token estimation and dashboard UI.  
→ **BACK DECOMPOSE T-HUB-078-context-budget-enforcement**
