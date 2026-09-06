# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-068-start-finish-transaction-boundary  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 7). Слито: red crash+tokenless handoff в s01 (один Independent Test contract); Kind I docs + leftover exception-only restore + CLI hatch → s06 purge (не отдельный s07). Apply≠purge: journal add (s02) ≠ wrap writers (s03) ≠ recover enforce (s04) ≠ leftover purge (s06). Lock (s05) — отдельный outcome US-003 / SC-004.

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-068-start-finish-transaction-boundary/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests as SoT) → s02 add (sidecar journal + states) → s03 wire (finish_implement + finish_qa) → s04 enforce (prepare_session recover, leftover `prepared` DENY start) → s05 lock (save_epic_state RMW) → s06 purge (A+B+C+I leftover + Kind I).  
> **Technology axiom pick (FR-001):** sidecar-only journal `.claude/runtime/epic/finish-tx.json` — **не** BOUNDARY_REGISTRY в этом эпике (less 066 coupling). Schema id in file = `loop-finish-transaction/v1`. extra=forbid on journal payload. Postgres N/A (FR-011).  
> **CREATIVE:** нет (`needs_creative: no` на всех шагах).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-type-safety` | journal payload extra=forbid, Literal states |
| `python-error-handling` | finish_handoff_forbidden, rollback_required, NEED_HUMAN corrupt journal |
| `python-resilience` | lockfile / concurrent save_epic_state (s05) |
| `python-observability` | recovery_token incident log (FR-007) |

**Per-step:** BACK — skills gate в каждом `sNN` (`workflow-decompose.mdc`). Session skills (`writing-plans`) **FORBIDDEN** в `impl:`.

## Requirements coverage

> **HARD:** каждый AC+ / AC− / FR / NFR (или UI AC для FRONT/INTEG) → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap/queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Schema `loop-finish-transaction/v1` (or `finish_transaction/v1`) in registry **or** sidecar-only documented; DECOMPOSE pick sidecar `.claude/runtime/epic/finish-tx.json` vs BOUNDARY_REGISTRY. Prefer sidecar journal first (less 066 coupling); if registered, extra=forbid. | s02 | **Pick: sidecar-only** `.claude/runtime/epic/finish-tx.json`. Not BOUNDARY_REGISTRY. extra=forbid on payload. |
| FR-002 | States: `prepared` → `context_written` → `index_written` → `committed`. Failure → `rollback_required`. | s02, s03 | measurable: pytest state machine + crash fixtures |
| FR-003 | Staged files in tx dir; commit = rename/replace all; fsync as existing atomic helper. | s02, s03 | wrap `atomic_write_text` / `os.replace`; not new DB |
| FR-004 | Identity check: staged Handoff epic_id/step_id == index target == state armed. | s02, s03 | Failure matrix TM-006 / QA TM-005 |
| FR-005 | `prepare_session` calls `recover_finish_transaction()`. | s04 | leftover journal → recover **before** inject |
| FR-006 | Public dispatcher: only `mb-finish implement\|qa\|bugfix\|…` typed. `handoff` subcommand removed or gated. | s01, s03, s06 | CLI without token → `finish_handoff_forbidden` |
| FR-007 | Internal `finish_handoff(..., recovery_token=)` validates token vs journal id; logs incident. | s03, s06 | hatch not public; token == journal id |
| FR-008 | Kind I: finish-block.mdc / docs mentioning handoff CLI as normal path — rewrite. | s06 | rg 0 operator paths |
| FR-009 | `save_epic_state` lockfile same family as spawn-gate **or** document single-threaded hook assumption with test that fails if unlocked lost-update reproduced. | s05 | lockfile family `_spawn_state_lock` |
| FR-010 | QA/bugfix finish functions share journal helper (not only implement) — minimum implement+qa; bugfix if same write pattern. | s03 | implement + qa wrap; bugfix same writer if dual-write |
| FR-011 | Do not require postgres; filesystem journal is SoT. | s02 | sidecar JSON file; no alembic |
| FR-012 | REFLECT finish path: **out** (060). If `finish_reflect` still exists, 068 must not reintroduce; journal helper ignores reflect. | s03, s06 | TM-008 ignore/out |
| FR-013 | Tests: crash after context; crash after index before committed marker; recover committed leftover (idempotent); token-less handoff. | s01, s04 | TM-001 / TM-002 / Independent Test |
| FR-014 | halt_logic / check_after unchanged behaviorally except they must not call public handoff. | s03, s06 | rg no public handoff from halt/check_after |
| FR-015 | Appetite cut: unified TransitionService class / ContextBoundaryService — design note in HOW, **no** mandatory new module tree. | s02 | covered as out_of_scope cut_list (no module tree); HOW note lives in plan |
| US-001 | Как operator, я не хочу Handoff без index commit после crash. | s01, s03, s04 | crash fixture → recover aligns files |
| US-001 Given/When/Then | Given: staged finish; context file replaced; kill before index. When: `prepare_session` / recover. Then: either both new or both old; never mixed identity (epic/step mismatch) | s01, s04 | AC−1 |
| US-002 | Как CI, я хочу public finish_handoff fail or require token. | s01, s03, s06 | CLI without token → error `finish_handoff_forbidden` |
| US-002 Given/When/Then | Given: `mb-finish handoff` or Python `finish_handoff` from CLI dispatcher. When: no `recovery_token`. Then: reject; state not armed | s01, s06 | AC−2 |
| US-003 | Как hook, я не теряю retry counter при concurrent save. | s05 | two writers fixture |
| US-004 | Как SessionStart, я доигрываю prepared journal. | s04 | leftover journal → recover before inject |
| SC-001 | crash recover consistent | s01, s04 | pytest |
| SC-002 | handoff without token rejected | s01, s06 | CLI/unit |
| SC-003 | prepare_session recovers | s04 | unit |
| SC-004 | concurrent state no silent drop | s05 | pytest or skip+lock |
| SC-005 | docs no public handoff | s06 | rg |
| AC+1 | Journaled finish for implement (and qa if same writer). | s03 | |
| AC+2 | Recover on prepare. | s04 | |
| AC+3 | Public finish_handoff closed. | s01, s06 | |
| AC+4 | Crash tests. | s01, s04 | |
| AC+5 | State lock or proven single-writer. | s05 | |
| AC−1 | Нет mixed Handoff/index identity after recover. | s01, s04 | |
| AC−2 | Нет CLI re-arm without verify. | s01, s06 | |
| AC−3 | Нет journal left `prepared` ignored on next start. | s04, s06 | |
| AC−4 | Нет reintroduction finish_reflect. | s03, s06 | |
| AC−5 | Нет «backup restore only on exception» as sole crash strategy. | s04, s06 | |
| Product spec 1 | Journal record for every implement/qa/bugfix finish: `prepared`, `context_written`, `index_written`, `committed`, `rollback_required`. | s02, s03 | |
| Product spec 2 | `prepare_session` / next SessionStart detects incomplete journal → complete or rollback **before** agent work. | s04 | |
| Product spec 3 | `finish_handoff` not on public CLI; internal only with `recovery_token`. | s01, s03, s06 | |
| Product spec 4 | Two concurrent `save_epic_state` cannot drop fields (lock or retry). | s05 | |
| Product spec 5 | Tests simulate crash-after-context-write. | s01 | |
| Technology axiom Finish commit | `finish_transaction/v1` journal prepared→committed; FORBIDDEN multi-file write without journal | s02, s03, s06 | |
| Technology axiom Public CLI | phase-typed `mb-finish <phase>` only; FORBIDDEN public `finish_handoff` re-arm | s01, s06 | |
| Technology axiom Recovery hatch | `recovery_token` + journal log; FORBIDDEN undocumented escape | s03, s06 | |
| Technology axiom State RMW | one lock for epic state + sidecars in finish path; FORBIDDEN unlocked concurrent save_epic_state | s05 | |
| Technology axiom Crash | prepare_session recovers/rolls back; FORBIDDEN split-brain accepted | s04 | |
| Failure matrix TM-001 | crash after context / split-brain / recover / align | s01, s04 | QA TM-001 |
| Failure matrix TM-002 | crash after index pre-marker / ambiguous / recover policy documented | s01, s04 | FR-013 second crash |
| Failure matrix TM-003 | public handoff / skip verify / CLI / forbidden | s01, s06 | QA TM-002 |
| Failure matrix TM-004 | stale journal ignored / start with mixed / prepare recover | s04 | QA TM-003 |
| Failure matrix TM-005 | lost-update state / counters / lock test | s05 | QA TM-004 |
| Failure matrix TM-006 | identity mismatch staged / wrong step / validate / abort tx | s02, s03 | QA TM-005 |
| Failure matrix TM-007 | recover loops / journal corrupt / fail-closed NEED_HUMAN | s04 | |
| Failure matrix TM-008 | 060 reflect finish / ImportError / ignore/out | s03, s06 | |
| QA TM-001 | crash after context / pytest tx / recovered consistent / US-001 | s01, s04 | |
| QA TM-002 | handoff no token / CLI/unit / finish_handoff_forbidden / US-002 | s01, s06 | |
| QA TM-003 | prepare recovers journal / unit / committed or rolled back / US-004 | s04 | |
| QA TM-004 | concurrent saves / pytest / no dropped field / US-003 | s05 | |
| QA TM-005 | identity mismatch abort / pytest / rollback_required / FR-004 | s02, s03 | |
| QA TM-006 | rg public handoff docs / rg / 0 operator paths / FR-008 | s06 | |
| Independent Test PASS | mixed files after simulated crash become aligned; CLI handoff without token fails. | s01, s04, s06 | |
| Independent Test FAIL | «atomic replace of one file» without multi-file journal; «backup on Exception» without prepare recover. | s01–s06 | dilution = FAIL ANALYZE |
| Appetite cut | TransitionService class tree; ContextBoundaryService rewrite; MCP-only finish; cross-host locks | — | `cut_list`; not steps |
| Out of scope | REFLECT deletion (T-HUB-060 IMPLEMENT); duplicate hooks (065); pack doctor (067) except consume incomplete-bundle if already landed; Codex TOML (069) | — | follow_up IDs in queue |
| NFR filesystem | Do not require postgres; filesystem journal is SoT (FR-011) | s02 | |
| NFR single machine | Single machine / single project dir (hub). NFS locks N/A. | s05 | documented; cross-host cut |

## Stages coverage

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Red: crash fixture + public handoff forbidden | plan §До DECOMPOSE 1 | s01 |
| Journal schema/sidecar + states | plan §До DECOMPOSE 2 · FR-001/002/003/004 | s02 |
| Wrap finish_implement (+ qa if same) | plan §До DECOMPOSE 3 · FR-010 | s03 |
| prepare_session recover | plan §До DECOMPOSE 4 · FR-005 | s04 |
| Lock save_epic_state | plan §До DECOMPOSE 5 · FR-009 | s05 |
| Kind I + purge CLI/docs | plan §До DECOMPOSE 6 · FR-008 | s06 |
| Purge exception-only as sole strategy comments/tests | plan §До DECOMPOSE 7 · AC−5 | s06 |
| Data flow: mb-finish phase → journal prepared → stage → identity → commit | plan §Data flow | s02, s03 |
| Data flow: crash → prepare_session recover | plan §Data flow | s04 |
| Data flow: finish_handoff CLI → forbidden unless recovery_token | plan §Data flow | s01, s06 |
| Ladder add | behavior-first §3 | s01, s02 |
| Ladder wire | behavior-first §3 | s03 |
| Ladder enforce | behavior-first §3 | s04, s05 |
| Ladder purge | behavior-first §3 · legacy-fallback-cleanup | s06 |
| Technology axiom lock (sidecar journal, typed CLI, recover, RMW lock) | plan §Technology axiom | s02–s06 |

## Outcome map

> **HARD:** не ужимать Goal/NFR плана до infra-slug. Map ≠ замена шагов.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Finish transition (activeContext + index/state + implement step) — **одна** recoverable транзакция | s02, s03, s04 |
| Crash между write context и `finalize_step` не оставляет split-brain | s01, s04 |
| Публичный `finish_handoff` не перевооружает workflow в обход verify/finalize | s01, s03, s06 |
| Concurrent hook state saves не last-write-lose silently | s05 |
| leftover `prepared` journal не игнорируется на SessionStart | s04, s06 |
| Mixed Handoff/index identity after recover — never | s01, s04 |
| Docs/rules не рекламируют handoff CLI как operator path | s06 |
| Independent Test PASS: crash aligned + tokenless CLI fails | s01 + s04 + s06 |
| Independent Test FAIL dilution: one-file atomic replace without journal; Exception-only backup without prepare recover | s01–s06 (не done) |
| Appetite cut: TransitionService OOP / ContextBoundaryService / MCP-only finish / cross-host locks | — (`cut_list`) |
| Out of scope: 060 REFLECT, 065 dual hooks, 067 pack doctor (consume only), 069 Codex TOML | queue / Assumptions |

## Replacement cleanup

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** `roadmap/queue.yaml`).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Kind B `mb-finish handoff` CLI: s01/s03 gate + s06 delete leftover help/docs.  
> `Kind`: A=code · B=entrypoint/deploy · C=fallback · **I=instruction surface**. Fallback?=yes → deletes in-epic.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| unjournaled dual write (`finish_implement_step` write context then `finalize_step` without journal) | A | journal helper `loop/mb_finish/transaction.py` | s03, s06 | no | sunset A |
| public `finish_handoff` re-arm without `recovery_token` | A | typed `mb-finish <phase>` / token vs journal id | s01, s03, s06 | no | sunset A |
| CLI `mb-finish handoff` public escape | B | removed or gated (`finish_handoff_forbidden`) | s01, s06 | no | sunset B |
| exception-only restore as sole crash strategy | C | `prepare_session` → `recover_finish_transaction()` | s04, s06 | yes | sunset C |
| unlocked `save_epic_state` concurrent last-write-lose | C | lockfile same family as spawn-gate | s05, s06 | yes | sunset C |
| docs «finish_handoff for operators» | I | recovery only | s06 | no | sunset I |
| finish-doc-router / finish-block advertising handoff escape as normal path | I | typed phases | s06 | no | sunset I |
| leftover comments/tests asserting backup-on-Exception is enough | A | rewrite crash+recover tests | s06 | no | plan s07 merged |
| `finish_reflect` reintroduction | A | ignore/out (060) | s06 | no | FR-012; keep 060 deletion |
| TransitionService class tree | — | — | — | — | Appetite cut_list |
| ContextBoundaryService rewrite | — | — | — | — | Appetite cut_list |
| MCP-only finish | — | — | — | — | Appetite cut_list |
| cross-host / NFS locks | — | — | — | — | Appetite cut_list; Assumptions NFS N/A |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-crash-handoff-red-contract.yaml](../yaml/steps/s01-crash-handoff-red-contract.yaml) | [s01…](../../implement/T-HUB-068-start-finish-transaction-boundary/s01-crash-handoff-red-contract.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-journal-sidecar-states.yaml](../yaml/steps/s02-journal-sidecar-states.yaml) | [s02…](../../implement/T-HUB-068-start-finish-transaction-boundary/s02-journal-sidecar-states.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-wrap-finish-implement-qa.yaml](../yaml/steps/s03-wrap-finish-implement-qa.yaml) | [s03…](../../implement/T-HUB-068-start-finish-transaction-boundary/s03-wrap-finish-implement-qa.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-prepare-session-recover.yaml](../yaml/steps/s04-prepare-session-recover.yaml) | [s04…](../../implement/T-HUB-068-start-finish-transaction-boundary/s04-prepare-session-recover.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-lock-save-epic-state.yaml](../yaml/steps/s05-lock-save-epic-state.yaml) | [s05…](../../implement/T-HUB-068-start-finish-transaction-boundary/s05-lock-save-epic-state.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-068-start-finish-transaction-boundary/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** `no` на всех шагах.  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
