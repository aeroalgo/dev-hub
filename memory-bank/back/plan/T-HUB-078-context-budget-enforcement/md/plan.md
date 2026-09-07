# T-HUB-078 — Исполнимый бюджет контекста и поиска

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft  
**Clarify:** Phase 0 skipped — taxonomy clear. **Prompt:** [md/prompt.md](prompt.md)

## Контекст и цель

Аудит обнаружил 500 Read в 12 активных сессиях, включая 105 повторных Read одного файла, 25/19 Read двух других файлов и повторную загрузку полного `plan.md` в lean IMPLEMENT. Текстовые правила уже запрещают это, но runner и tool boundary не измеряют и не блокируют нарушение.

Цель: обычный IMPLEMENT получает минимальный, воспроизводимый контекст и не может бесконтрольно reread, загрузить monolithic plan или выполнить поиск за file allowlist без явного graphify-backed исключения.

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

## AC

1. Repeating the same full Read in IMPLEMENT is blocked/cached and `duplicate_reads=0` at finish.
2. A plan jump succeeds while whole plan Read is denied in IMPLEMENT.
3. Search inside shard paths works; search outside requires graphify evidence and records its reason.
4. A real code edit permits a narrow post-edit diff read, not silent stale caching.
5. Telemetry distinguishes allowed reads, denied rereads and approved exceptions without storing secret file content.

### AC−

- No hidden global bypass for `Read`, `rg`, `cat`, Python file reads or wrapper aliases.
- No failure mode that silently falls back to full plan/read-all-memory-bank.
- No test cache reuses a command after relevant files changed.

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

Ledger is an enforcement service used by the tool wrappers, not prose parsed from agent messages. It records metadata only; content remains in normal tool results. ScopeResolver is pure/testable and receives no agent-authored wildcard as authority.

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

- Define serialized `ContextReadRecord` and pure decision function with modes PLAN/IMPLEMENT/TASK/BUGFIX/QA.
- Instrument supported Read routes; normalize symlinks, relative paths and ranges before comparison.
- Write Red tests for repeat full Read, post-edit narrow Read and path-alias bypass; implement minimal green behavior.

### Stage 2 — plan-jump projection and monolith guard

- Parse shard `plan_contract.plan_jumps`, materialize exact permitted excerpts and attach their identity to prompt/session state.
- Reject whole plan paths in lean code modes with a diagnostic naming the valid jump.
- Preserve full plan access for PLAN/DECOMPOSE/ANALYZE/AUDIT, where it is legitimate.

### Stage 3 — search and test execution contracts

- Build ScopeResolver from shard files/delta/parent dirs; support graphify receipt validation for expanded search.
- Fingerprint test execution by normalized command and relevant changed paths; emit cache/no-op evidence instead of hiding repeats.
- Add policy tests covering `rg`, tool aliases and Python-wrapper read/search invocations that bypass simple string matching.

### Stage 4 — metrics, migration and purge

- Expose finish-safe metrics in handoff/diagnostic output; establish budgets as warnings first, then enforce after baseline.
- Remove duplicate context-counting/prompt prose that conflicts with ledger decisions.
- Regression-test a real shard flow: one allowed code map, one TDD cycle, no monolithic plan and no duplicate full Read.

## QA consumes

| ID | Priority | Scenario | Expected | Maps |
|---|---|---|---|---|
| TM-078-01 | P0 | same full path/range/hash twice | deny/cache, metric increments | FR-001 |
| TM-078-02 | P0 | file changed then narrow read | allowed with diff evidence | FR-002 |
| TM-078-03 | P0 | IMPLEMENT whole plan vs jump | plan denied, jump allowed | FR-003 |
| TM-078-04 | P0 | search beyond files | deny until graphify receipt | FR-004 |
| TM-078-05 | P1 | repeated test then changed diff | cache then rerun | FR-006 |
| TM-078-06 | P1 | finish telemetry | exact aggregate fields | FR-005 |

## Review readiness

All required rows are done: Product probe, data flow/failure matrix, delivery closure, QA matrix and plan review. No unresolved CRITICAL ambiguity.

## Appetite and next mode

`timebox_days: 3`; cut first: adaptive token estimation and dashboard UI.  
→ **BACK DECOMPOSE T-HUB-078-context-budget-enforcement**
