# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-078-context-budget-enforcement  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-07  
**Режим:** BACK DECOMPOSE

Каждый `sNN` — атомарная production capability с outcome-first goal, полным delta layer, plan contract, TDD внутри шага и измеримыми checkpoints. Layout v2: shards находятся в `yaml/steps/`; `decompose-index.yaml` — единственный источник статуса.

## Skills в контексте

| Skill | Зачем |
|---|---|
| `writing-plans` | Структура и атомарность decompose-артефакта; сессионный skill, не передаётся в IMPLEMENT. |
| BACK Impl Core | `tdd`, `python-testing-patterns`, `modern-python`, `python-anti-patterns` присутствуют в каждом production shard. |
| Situational | На каждом shard выбраны только skills из BACK allowlist по surface: async, type-safety, resilience, observability, configuration. |

**Per-step:** итоговый `skills.impl` хранится в каждом YAML и является источником обязательных Read для BACK IMPLEMENT. Нет UI; `needs_creative: "no"` во всех шагах.

## Requirements coverage (plan → steps)

> Каждая FR/AC+/AC−/NFR плана имеет shard с verbatim ID/цитатой и measurable checkpoint. Product FR закрываются production entrypoint + failure behavior, а не одним resolver/metadata unit.

| Req ID | Plan FR/AC/NFR text (verbatim or operative quote) | sNN | Evidence / coverage |
|---|---|---|---|
| FR-001 | session ledger хранит canonical realpath, content hash/version, range, purpose и sequence Read; повтор полного неизменённого Read получает denial/cached reference | s01, s06 | s01 cp1/cp3; s06 cp1/cp6; shared ledger is wired and old ad-hoc path is purged |
| FR-002 | после Edit допускается только diff или declared symbol/range; новый full Read требует explicit exception reason | s02, s01 | s02 cp2; s01 cp2/cp3; write boundary invalidates old ranges |
| FR-003 | PLAN runner materializes `plan_jumps` into bounded excerpts; IMPLEMENT Read whole `md/plan.md` denied unless plan-mode/approved exception | s03, s05, s06 | s03 cp1/cp4; s05 cp3; s06 cp2/cp3 |
| FR-004 | search command derives allowlist from shard `files`, declared delta and parent dirs; выход за неё требует successful graphify query plus typed reason | s03, s05, s06 | s03 cp2/cp4; s05 cp3; s06 cp3/cp4 |
| FR-005 | end-of-session telemetry reports `unique_reads`, `duplicate_reads`, bytes/ranges, monolith-plan attempts, search exceptions and highest-repeat path | s04, s06 | s04 cp1/cp2/cp4; s06 cp1/cp4 |
| FR-006 | targeted test command results are fingerprinted by command + relevant diff; exact repeat without changed inputs returns cached result or explicit no-op record | s03, s06 | s03 cp3/cp4; s06 cp3/cp5 |
| FR-007 | один и тот же ledger policy применяется к root-agent и каждому subagent в Claude Code и Codex; различия provider payload не меняют duplicate/read-after-edit semantics | s02, s04, s05, s06 | s02 cp1/cp3; s04 cp3; s05 cp1/cp2; s06 cp4/cp6 |
| FR-008 | ledger scope различает `(project, root session, actor invocation)` и не переносит факт чтения между parent/child автоматически | s01, s02, s04 | s01 cp1; s02 cp2; s04 cp1/cp3 |
| FR-009 | после успешного изменения или обнаружения внешнего изменения файла прежние ranges этого файла недействительны до подтверждения новой content hash | s01, s02, s06 | s01 cp3; s02 cp2; s06 cp6 |
| FR-010 | повторный полный Read либо Read диапазона возвращает machine-readable decision receipt с разрешёнными решениями, reason code и canonical path, но никогда не включает содержимое файла | s01, s02, s04, s05 | s01 cp1/cp2/cp4; s02 cp1/cp3; s04 cp1/cp2; s05 cp3 |
| AC+ #1 | Repeating the same full Read in IMPLEMENT is blocked/cached, increments `duplicate_reads`, and cannot produce a second full context payload | s01, s04, s06 | s01 cp1; s04 cp1; s06 cp1/cp6 |
| AC+ #2 | A plan jump succeeds while whole plan Read is denied in IMPLEMENT | s03, s05 | s03 cp1; s05 cp3 |
| AC+ #3 | Search inside shard paths works; search outside requires graphify evidence and records its reason | s03, s05 | s03 cp2; s05 cp3 |
| AC+ #4 | A real code edit permits a narrow post-edit diff read, not silent stale caching | s01, s02 | s01 cp2/cp3; s02 cp2 |
| AC+ #5 | Telemetry distinguishes allowed reads, denied rereads and approved exceptions without storing secret file content | s04, s06 | s04 cp1/cp2; s06 cp4 |
| AC+ #6 | Root-agent and two subagents reading the same unchanged range receive independent, deterministic decisions in both Claude and Codex fixtures | s01, s02, s04, s05 | s01 cp1; s02 cp1/cp2; s04 cp3; s05 cp1 |
| AC+ #7 | A write by root-agent invalidates the same file for root-agent and subagents; each actor may read the new version once, then duplicate protection applies again | s01, s02, s04 | s01 cp3; s02 cp2; s04 cp3 |
| AC+ #8 | Provider event aliases (`Read`/`read`, `Edit`/`Write` and equivalent Codex payloads) converge to the same normalized request and decision | s02, s05 | s02 cp1/cp3; s05 cp1 |
| AC− #1 | No hidden global bypass for `Read`, `rg`, `cat`, Python file reads or wrapper aliases | s03, s05, s06 | s03 cp2/cp4; s05 cp2/cp4; s06 cp3/cp6 |
| AC− #2 | No failure mode that silently falls back to full plan/read-all-memory-bank | s03, s04, s05, s06 | s03 cp1/cp4; s04 cp2; s05 cp4; s06 cp2/cp3 |
| AC− #3 | No test cache reuses a command after relevant files changed | s03, s06 | s03 cp3; s06 cp5 |
| AC− #4 | No process-local-only ledger that disappears between hook invocations | s01, s04 | s01 cp4; s04 cp2 |
| AC− #5 | No provider-specific bypass through child agents, aliases, wrapper commands or a second hook registration | s02, s05, s06 | s02 cp3/cp4; s05 cp2; s06 cp4/cp6 |
| NFR: fail-closed | hash unavailable, pre/post mismatch, persistence failure, provider mismatch and finish write failure do not become silent green | s01, s02, s04, s06 | s01 cp3; s02 cp3; s04 cp2; s06 cp3/cp6 |
| NFR: parity | Claude and Codex differ only in transport input/output format | s02, s05 | s02 cp1; s05 cp1/cp2 |
| NFR: observable | decisions are attributable and counters contain metadata only | s01, s04, s05 | s01 cp4; s04 cp1/cp2; s05 cp3 |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Source | sNN | Measurable closure |
|---|---|---|---|
| Stage 1 — ledger and read policy | plan §231–239 | s01 | cp1–cp4: policy, interval algebra, persistence, TDD cases |
| Canonical path, content hash and interval algebra | plan §58–72 | s01 | cp2/cp3: aliases, EOF, overlap, unknown hash, invalidation |
| Durable atomic storage and actor/session key | plan §68–72, §134 | s01 | cp3/cp4: lock, restart, metadata-only state |
| Stage 2 — plan-jump projection and monolith guard | plan §240–246 | s03 | cp1/cp4: bounded jump and whole-plan denial |
| Root/subagent mode parity for plan access | plan §244–245 | s03, s05 | s03 cp1; s05 cp1/cp3 |
| Stage 3 — search and test execution contracts | plan §247–253 | s03 | cp2/cp3/cp4: search aliases, graphify receipt, changed fingerprint |
| Claude/Codex adapter fixtures | plan §251–253 | s02, s05 | s02 cp1/cp3; s05 cp1/cp2 |
| Write invalidation at every supported boundary | plan §253 | s02, s01 | s01 cp3; s02 cp2 |
| Stage 4 — metrics, migration and purge | plan §255–261 | s04, s05, s06 | s04 cp1/cp2; s05 cp1–cp3; s06 cp1–cp6 |
| Finish-safe metrics and baseline → enforce | plan §257 | s04 | cp1/cp2/cp4: non-green on metric failure |
| Remove conflicting duplicate counters/prose | plan §258, §261 | s05, s06 | s05 cp4; s06 cp1/cp4/cp6 |
| Regression real shard flow | plan §259 | s05 | cp3: production entrypoints and success/failure |
| Materialize shared contract in Claude/Codex | plan §260 | s02, s05 | s02 cp4; s05 cp1/cp2 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги | Почему это production outcome |
|---|---|---|
| Повторное чтение больше не создаёт скрытый второй context payload | s01, s02, s04, s06 | Shared ledger decision reaches provider response and finish counters; purge prevents optional fallback. |
| Легитимная narrow investigation остаётся возможной после Edit | s01, s02, s03 | New content version, partial range and declared jump are accepted only with evidence. |
| Whole plan and broad search cannot be loaded by convenience | s03, s05, s06 | Production preflight denies monolith/out-of-scope aliases; generated contracts cannot weaken it. |
| Claude Code and Codex have equivalent decisions | s02, s05 | Transport adapters normalize to one policy and parity checker rejects drift. |
| Root and subagent lifecycle remains actor-attributable | s01, s02, s04 | Durable key, invalidation event and aggregate preserve invocation lineage. |
| Finish cannot claim green with missing/corrupt context evidence | s04, s06 | Receipt projection is fail-closed and old counters/fallbacks are purged. |
| Test execution does not hide stale results | s03, s06 | Relevant-diff fingerprint controls cache/no-op and purge keeps one SoT. |
| Out of scope: adaptive token estimation and dashboard UI | — | Appetite cut in plan; not a deferred product requirement and no follow-up is needed. |

## Replacement cleanup (plan → steps)

> Brownfield replacement follows `add → wire → enforce → purge`. Every sunset row has a concrete owner with `deletes:` and a final scan. Obsolete tests and Kind I instruction surfaces are included in the final purge; no shim or optional SoT remains.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes / verification |
|---|---:|---|---|:---:|---|
| `untracked Read/tool usage` and `ad-hoc context counting` | A | shared ContextLedger + typed metrics producer | s01 adds/wires; s06 deletes | no | s06 cp1 + cp6 inventory/import-audit |
| `raw runner injection of plan path` | B | bounded generated plan-jump excerpt | s03 wires; s06 deletes | no | s03 cp1/cp4; s06 cp2 |
| `policy failure → broad read/search` | C | explicit deny or typed exception receipt | s03/s04 enforce; s06 deletes | yes | s03 cp2; s04 cp2; s06 cp3 |
| `prose-only reread/graphify guidance` | I | runner-enforced shared contract + concise diagnostic | s05 rewrites; s06 deletes obsolete wording | no | s05 cp1/cp4; s06 cp4 |
| `provider-local duplicate-read counters` | A/I | shared receipt aggregate | s04 wires; s06 deletes | no | s04 cp4; s06 cp1/cp4 |
| obsolete tests asserting broad-read/provider-local behavior | A/I | production boundary tests for deny/receipt | s03–s05 rewrite; s06 deletes remaining | no | s06 cp5 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
|---|---|---|:---:|:---:|---|---|
| **s01** | [s01-context-ledger-policy.yaml](../yaml/steps/s01-context-ledger-policy.yaml) — ContextLedger and range policy | — | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-provider-adapters-and-invalidation.yaml](../yaml/steps/s02-provider-adapters-and-invalidation.yaml) — Claude/Codex parity and invalidation | — | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-plan-jump-search-and-test-scope.yaml](../yaml/steps/s03-plan-jump-search-and-test-scope.yaml) — bounded context and search/test scope | — | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-telemetry-and-finish-projection.yaml](../yaml/steps/s04-telemetry-and-finish-projection.yaml) — finish-safe metrics | — | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-contract-materialization-and-regression-flow.yaml](../yaml/steps/s05-contract-materialization-and-regression-flow.yaml) — generated parity and real flow | — | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) — final A/B/C/I purge | — | no | no | BACK IMPLEMENT | pending |

**Next:** `BACK ANALYZE T-HUB-078-context-budget-enforcement`; IMPLEMENT не начинается до `validate-decompose-tree` exit 0, `validate-traceability` `CRITICAL=0` и обязательного ANALYZE с `critical_count=0`.
