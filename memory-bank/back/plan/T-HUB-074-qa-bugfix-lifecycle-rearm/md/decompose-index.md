# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-074-qa-bugfix-lifecycle-rearm  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-07  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red в s01; finish_qa next_mode+parse в s02; finish_handoff+roadmap-advance enforce в s03; purge finish_reflect/find_reflection_artifact в s04; Kind I + mb-finish reflect entrypoint в s05; apply≠purge leftover inventory в s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-074-qa-bugfix-lifecycle-rearm/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests fail≠DONE / reuse yaml / handoff escape / missing verdict / new session / reviewer lock) → s02 add+wire+enforce (`finish_qa` next_mode BUGFIX only; `parse_qa_verdict` missing ≠ pass; keep `qa_new_*` + reviewer) → s03 wire+enforce (`finish_handoff` `qa_fail_blocks_handoff`; `roadmap_advance` `qa_fail_blocks_advance` if leave-on-fail) → s04 purge Kind A `finish_reflect` / `find_reflection_artifact` + obsolete tests → s05 Kind I + Kind B mb-finish reflect subcommand/MCP → s06 leftover inventory scan (apply≠purge).  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s02 finish_qa ≠ s03 escape hatch (handoff/queue); s04 symbol purge ≠ s05 instruction/entrypoint; TDD red is s01 not a seventh tests-only step; s06 purge leftover after apply.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | fail-closed diagnostics (`qa_fail_blocks_*`, missing verdict) |
| `python-type-safety` | `parse_qa_verdict` enum; no prose SoT |
| `python-observability` | diagnostic_codes on fail paths (s02/s03) |

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC / TM → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap/queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

## Requirements coverage (plan → steps)

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | `finish_qa` fail/blocked → `next_mode="BUGFIX"` only. Never `"DONE"`, never `"REFLECT"`. | s01, s02, s06 | Independent Test core |
| FR-002 | Keep `qa_new_session_required` and `qa_new_artifact_required`. Add tests that fail if those branches deleted. | s01, s02, s06 | already coded; lock |
| FR-003 | `finish_handoff`: if latest qa for armed epic is fail/blocked and requested meta.mode in `{DONE, IMPLEMENT, ANALYZE, DECOMPOSE, PLAN, QA}` except BUGFIX — `ok=False` `qa_fail_blocks_handoff`. BUGFIX allowed (already bugfix_finish_required inverse). | s01, s03, s06 | escape hatch |
| FR-004 | `finish_bugfix` must set `QaAfterBugfix` so subsequent QA cannot skip (already). Test: after finish_bugfix, finish_qa without new yaml fails. | s01, s02 | TM-008 |
| FR-005 | Purge `finish_reflect` function if still present; purge imports; rewrite `harness/hooks/tests/test_mb_finish_*.py` ISS-002 class. | s04, s05, s06 | Kind A |
| FR-006 | Purge `find_reflection_artifact` or make it raise unused — **delete**. | s04, s06 | Kind A |
| FR-007 | Kind I: workflow comments next QA = REFLECT **in mb_finish / epic core** — delete. Rules mdc leftovers outside hooks — only if rg in loop/harness; `.cursor/rules` only if one-line and blocks tests (prefer 070 for overlay; this epic for Python finish_*). | s05, s06 | Kind I; overlay 070 follow_up |
| FR-008 | Do not auto-requeue T-HUB-060 (Appetite cut). Machine gate is forward-looking. | — | Appetite cut_list; not a step |
| FR-009 | parse_qa_verdict fail-closed: missing verdict ≠ pass. | s01, s02, s06 | as-built `if qa_art else "pass"` sunset |
| FR-010 | Tests under `loop/tests/` and/or `harness/hooks/tests/` with tmp mb layout. | s01, s02, s03 | layout |
| FR-011 | Independent Test = cannot leave with fail yaml; not «QaAfterBugfix field exists». | s01, s02, s03, s06 | anti-dilution |
| FR-012 | If `finish_qa` pass path requires reviewer (L183–197) — keep; do not weaken. | s01, s02 | TM-006 |
| FR-013 | Queue/roadmap-advance: if a Python entrypoint advances queue on epic DONE, it must check latest qa pass. Locate in DECOMPOSE (`roadmap_queue.py` / `epic_transition`). If no such call — FR-003 handoff gate is the wedge. | s03, s06 | `roadmap_advance` marks done without qa pass today |
| FR-014 | No feature flag `ALLOW_QA_FAIL_DONE`. | s02, s06 | AC− dual path |
| FR-015 | FRONT/INTEG finish_qa same functions — one fix. | s02, s03 | shared `finish_qa` / `finish_handoff` |
| US-001 | Как QA fail, я иду в BUGFIX, не DONE. | s01, s02 | Given/When/Then finish_qa |
| US-002 | Как BUGFIX done, я не закрываю QA старым fail yaml. | s01, s02 | `qa_new_artifact_required` |
| US-003 | Как operator, finish_handoff не DONE при fail yaml. | s01, s03 | `qa_fail_blocks_handoff` |
| US-004 | Как CI, нет import finish_reflect. | s04, s05, s06 | rg 0 production |
| US-005 | Как reviewer, new QA after bugfix needs own reviewer PASS (already partial). | s01, s02 | keep `qa_reviewer_required` |
| SC-001 | fail qa → BUGFIX not DONE | s01, s02 | pytest |
| SC-002 | reuse yaml after bugfix rejected | s01, s02 | pytest |
| SC-003 | finish_handoff DONE blocked on fail yaml | s01, s03 | pytest |
| SC-004 | no finish_reflect import | s04, s05, s06 | rg |
| SC-005 | qa_reviewer_required still on re-QA | s01, s02 | pytest |
| AC+1 | QA fail cannot DONE. | s01, s02, s03 | |
| AC+2 | Re-QA after bugfix requires new yaml + session. | s01, s02 | |
| AC+3 | finish_reflect purged from production. | s04, s05, s06 | |
| AC+4 | Escape hatch cannot skip fail yaml. | s01, s03, s06 | |
| AC+5 | Tests encode 060-shaped leftover (fail yaml + bugfix prose). | s01, s02 | prose not SoT |
| AC−1 | Нет DONE после fail yaml. | s01, s02, s03, s06 | |
| AC−2 | Нет REFLECT next from finish_qa. | s01, s02, s05, s06 | |
| AC−3 | Нет shim `finish_reflect = finish_qa`. | s04, s06 | |
| AC−4 | Нет reuse fail artifact as pass. | s01, s02 | |
| AC−5 | Нет «bugfix.md 1942 passed» as verdict SoT. | s01, s02 | axiom |
| AC−6 | Нет dual path finish_handoff that writes DONE anyway. | s01, s03, s06 | |
| NFR-1 | Fail-closed epic leave | s02, s03, s06 | |
| NFR-2 | No dead REFLECT imports | s04, s05, s06 | |
| NFR-3 | Re-QA cost = new session (explicit), not hidden | s01, s02 | |
| TM-001 | P0 fail yaml → BUGFIX pytest finish_qa mode BUGFIX | s01, s02 | US-001 FR-001 |
| TM-002 | P0 reuse yaml after bugfix pytest qa_new_artifact_required | s01, s02 | US-002 FR-002 |
| TM-003 | P0 handoff DONE on fail pytest ok false | s01, s03 | US-003 FR-003 |
| TM-004 | P0 rg finish_reflect 0 production | s04, s05, s06 | US-004 FR-005 |
| TM-005 | P0 qa_new_session_required pytest ok false | s01, s02 | FR-002 |
| TM-006 | P1 qa_reviewer_required re-QA pytest ok false without PASS | s01, s02 | FR-012 |
| TM-007 | P1 missing verdict ≠ pass pytest fail-closed | s01, s02, s06 | FR-009 |
| TM-008 | P1 finish_bugfix sets QaAfterBugfix pytest subsequent QA gated | s01, s02 | FR-004 |
| Failure TM-001 | fail → DONE epic leave dirty | s01, s02, s03 | FAIL |
| Failure TM-002 | reuse fail yaml false pass | s01, s02 | FAIL |
| Failure TM-003 | finish_handoff escape skip gate | s01, s03 | FAIL |
| Failure TM-004 | finish_reflect import 060 ISS-001 | s04, s06 | FAIL |
| Failure TM-005 | missing new session same session close | s01, s02 | FAIL |
| Failure TM-006 | reviewer skipped on re-QA false green | s01, s02 | FAIL |
| Failure TM-007 | overlay REFLECT wrong next | — | follow_up: T-HUB-070-phase-policy-overlay-sole-sot (hard dep, queue) |
| Failure TM-008 | parse missing verdict as pass false green | s01, s02, s06 | FAIL |
| Independent Test PASS | fail yaml cannot DONE; re-QA needs new yaml; rg finish_reflect 0 | s01, s02, s03, s04, s06 | |
| Independent Test FAIL | «qa_after_bugfix field already exists» without tests that escape hatch is closed | s01, s03, s06 | dilution = FAIL ANALYZE |
| Product WHAT-1 | `finish_qa` with fail/blocked → `ok=true` only as **transition to BUGFIX**, never DONE, never `EPIC_DONE` hint. | s01, s02 | |
| Product WHAT-2 | Attempt to finish_qa pass while latest artifact is the **same** fail yaml after bugfix → `qa_new_artifact_required` | s01, s02 | |
| Product WHAT-3 | `finish_handoff` cannot write mode=DONE/IMPLEMENT/QA success while `armed_step=QA` and latest qa verdict fail | s01, s03 | |
| Product WHAT-4 | `roadmap-advance` / queue leave: if called after QA fail without BUGFIX — `ok=false` diagnostic `qa_fail_blocks_advance` (or reuse existing code). If no such function yet, gate in `finish_qa` is enough **plus** test that DONE handoff rejected. | s03, s06 | as-built `roadmap_advance` marks done without qa check |
| Product WHAT-5 | Purge live `finish_reflect` / `find_reflection_artifact` imports and tests. Rewrite tests to `finish_qa` next BUGFIX/DONE. | s04, s05, s06 | |
| Product WHAT-6 | T-HUB-060 leftover: do **not** rewrite 060 IMPLEMENT; do **purge hub code** that still imports reflect finish. Historical qa yaml on disk may stay fail (archive) — **machine** must not treat it as current pass. | s04, s06 | Appetite: no rewrite historical yaml |
| Technology axiom QA verdict | `parse_qa_verdict(qa-*.yaml)` enum pass/fail/blocked | s01, s02 | FORBIDDEN prose «1942 passed» in bugfix.md as SoT |
| Technology axiom Re-QA after bugfix | new yaml path ∉ `existing_artifacts` + new session | s01, s02 | FORBIDDEN reuse fail yaml to close |
| Technology axiom Epic leave | latest qa pass **or** explicit BUGFIX armed | s02, s03 | FORBIDDEN queue advance on fail yaml |
| Technology axiom REFLECT finish | gone | s04, s05, s06 | FORBIDDEN `from … import finish_reflect` / `find_reflection_artifact` live |
| Technology axiom next after QA fail | BUGFIX | s01, s02, s05 | FORBIDDEN REFLECT (070) / DONE |
| Out overlay REFLECT strings | Out: overlay string REFLECT (070 deletes it) | — | follow_up: T-HUB-070-phase-policy-overlay-sole-sot (queue, hard dep) |
| Out identity COMMAND | Out: identity COMMAND (071) | — | follow_up: T-HUB-071-session-identity-lock (queue) |
| Out load_session | Out: load_session ok (072) | — | follow_up: T-HUB-072-context-bundle-fail-closed (queue) |
| Out abort 401 | Out: abort 401 (073) | — | follow_up: T-HUB-073-abort-classifier-dirty-halt (queue) |
| Out finish journal schema | Out: finish journal schema (068) | — | follow_up: T-HUB-068-start-finish-transaction-boundary (queue) |
| Appetite requeue T-HUB-060 | Do not auto-requeue T-HUB-060 | — | cut_list; FR-008 |
| Appetite rewrite historical qa yaml | rewrite historical qa yaml bodies | — | cut_list |
| Appetite auto-open BUGFIX from audit | auto-open BUGFIX from audit docs | — | cut_list |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Technology axiom lock (verdict yaml / re-QA / epic leave / REFLECT gone) | plan §Technology axiom | s01, s02, s03, s04 |
| Red tests Independent Test | plan §До DECOMPOSE 1 | s01 |
| finish_qa next_mode lock + parse fail-closed | plan §До DECOMPOSE 2 | s02 |
| finish_handoff qa_fail_blocks_handoff + roadmap-advance | plan §До DECOMPOSE 3 · FR-013 | s03 |
| purge finish_reflect / find_reflection_artifact + tests | plan §До DECOMPOSE 4 | s04 |
| Kind I rg + mb-finish reflect subcommand | plan §До DECOMPOSE 5 | s05 |
| purge leftover comments / inventory | plan §До DECOMPOSE 6 | s06 |
| Data flow finish_qa → parse → qa_after_bugfix → fail BUGFIX / pass DONE | plan §Data flow | s02 |
| Data flow finish_handoff latest qa fail mode≠BUGFIX ok false | plan §Data flow | s03 |
| Data flow imports no finish_reflect | plan §Data flow | s04, s05 |
| Failure matrix 8 rows | plan §Failure matrix | s01–s06 (mapped per TM; TM-007 = 070) |
| Replacement A+B+C+I | plan §Replacement / sunset | s02–s06 |
| Wire-complete Add→Wire→Enforce→Purge | behavior-first §3 | s01 add tests → s02 wire finish_qa → s03 enforce escape → s04–s06 purge |
| Independent Test PASS/FAIL | plan §Independent Test | s01, s02, s03, s04, s06 |
| QA consumes TM-001…TM-008 | plan §QA consumes | s01–s06 |
| FRONT/INTEG same functions | plan FR-015 | s02, s03 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| QA fail yaml cannot mark epic DONE / dequeue / leave queue as success | s01, s02, s03 |
| After finish_bugfix, next QA requires new session + new `qa-*.yaml` | s01, s02 |
| Epic cannot advance past QA while latest qa yaml is fail and no newer pass | s02, s03 |
| Leftover `finish_reflect` / `find_reflection_artifact` purged — no live import | s04, s05, s06 |
| Kind I: overlay QA→REFLECT is 070; this epic purges remaining finish_reflect symbols + stale-yaml gate | s04, s05, s06 |
| `finish_qa` fail → BUGFIX only; never DONE; never EPIC_DONE hint; never REFLECT | s01, s02 |
| `parse_qa_verdict` missing verdict ≠ pass (no `if qa_art else "pass"`) | s01, s02, s06 |
| Escape hatch `finish_handoff` cannot DONE/IMPLEMENT/QA on fail yaml | s01, s03, s06 |
| `roadmap_advance` cannot mark current epic done while latest qa fail | s03, s06 |
| No `ALLOW_QA_FAIL_DONE`; no dual path; no shim `finish_reflect = finish_qa` | s02, s04, s06 |
| NFR-1 Fail-closed epic leave | s02, s03, s06 |
| NFR-2 No dead REFLECT imports | s04, s05, s06 |
| NFR-3 Re-QA cost = new session (explicit), not hidden | s01, s02 |
| Independent Test FAIL path («QaAfterBugfix field already exists» without escape tests) | s01, s03, s06 |
| Appetite cuts (requeue 060 / rewrite historical yaml / auto-open BUGFIX from audit) | — cut_list, не шаги |
| Overlay 070 / identity 071 / load_session 072 / abort 073 / journal 068 | — follow_up queue |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Финальный `*-legacy-fallback-purge` в очереди с `sunset_inventory` + `grep_control`.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `finish_reflect` | A | gone; use `finish_qa` | s04, s06 | no | FR-005; as-built already absent in `loop/mb_finish` — lock + leftover scan |
| `find_reflection_artifact` | A | gone | s04, s06 | no | FR-006 |
| tests importing `finish_reflect` | A | `finish_qa` tests (BUGFIX/DONE) | s01, s04, s06 | no | ISS-002 rewrite |
| DONE on qa fail (`next_mode="DONE"` / `epic_done=True` / `EPIC_DONE` hint) | A | BUGFIX | s02, s06 | no | FR-001; as-built fail branch already BUGFIX — lock + tests |
| `parse_qa_verdict(...) if qa_art else "pass"` | A | missing artifact / missing verdict → not pass | s02, s06 | no | FR-009; `impl.py:210` sunset |
| `roadmap_advance` mark-done while latest qa fail | A | `qa_fail_blocks_advance` | s03, s06 | no | FR-013; `require_done=False` leave |
| mb-finish reflect subcommand / MCP `finish_reflect` if still registered | B | removed | s05, s06 | no | plan B; as-built MCP has no reflect — lock |
| `finish_handoff` DONE despite fail yaml | C | `qa_fail_blocks_handoff` | s03, s06 | yes | FR-003; 068 token lock complementary, tests still required |
| ImportError catch continue on missing reflect | C | purge symbol | s04, s06 | yes | 060 ISS-001 |
| `ALLOW_QA_FAIL_DONE` / dual path | C | delete in-epic | s02, s06 | yes | FR-014 |
| QA FINISH → REFLECT in Python comments (`loop/mb_finish`, `epic/core`) | I | BUGFIX/DONE | s05, s06 | no | FR-007; overlay strings → 070 |
| prose «1942 passed» as verdict SoT | I | `parse_qa_verdict` yaml enum | s01, s02 | no | axiom; tests encode 060 leftover |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-qa-fail-lifecycle-red-tests.yaml](../yaml/steps/s01-qa-fail-lifecycle-red-tests.yaml) | [s01…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s01-qa-fail-lifecycle-red-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-finish-qa-next-mode-parse-fail-closed.yaml](../yaml/steps/s02-finish-qa-next-mode-parse-fail-closed.yaml) | [s02…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s02-finish-qa-next-mode-parse-fail-closed.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-handoff-roadmap-qa-fail-blocks.yaml](../yaml/steps/s03-handoff-roadmap-qa-fail-blocks.yaml) | [s03…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s03-handoff-roadmap-qa-fail-blocks.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-purge-finish-reflect-symbols.yaml](../yaml/steps/s04-purge-finish-reflect-symbols.yaml) | [s04…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s04-purge-finish-reflect-symbols.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-kind-i-mb-finish-reflect-entrypoint.yaml](../yaml/steps/s05-kind-i-mb-finish-reflect-entrypoint.yaml) | [s05…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s05-kind-i-mb-finish-reflect-entrypoint.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-074-qa-bugfix-lifecycle-rearm/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-074-qa-bugfix-lifecycle-rearm` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
