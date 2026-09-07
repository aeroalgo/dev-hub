# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-073-abort-classifier-dirty-halt  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red в s01; add permanent+delete catch-all в s02; wire+enforce loop halt в s03; dirty yaml glob в s04; DSH+Kind I в s05; apply≠purge → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-073-abort-classifier-dirty-halt/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests 401/banned/catch-all/timeout) → s02 add+enforce (`_AUTH_BANNED_PATTERNS` + delete catch-all + unknown fail-closed) → s03 wire (loop honor retryable=False; last-session keys) → s04 dirty epic glob yaml+md → s05 DSH parity + Kind I → s06 leftover inventory scan (apply≠purge).  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s02 classifier ≠ s03 loop consumer; s04 dirty_files is independent product FR (US-004); s05 DSH+Kind I ≠ s06 leftover inventory; TDD red is s01 not a seventh tests-only step.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | permanent vs transient abort outcomes |
| `python-resilience` | loop retry/halt (s03) |
| `python-type-safety` | shared pattern tuples / SessionAnalysis (s02, s05) |

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap-*.queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Remove `re.compile(r"(?i)API Error:[^\n]*")` from `_TRANSIENT_ABORT_PATTERNS`. Kind I: tests that relied on catch-all for generic API Error → rewrite to UNKNOWN or specific pattern. | s01, s02, s06 | catch-all sunset |
| FR-002 | Add to `_PERMANENT_FAILURE_PATTERNS` (or dedicated NEED_HUMAN set consumed as non-retryable): `(?i)API Error:\s*401\b` ; `(?i)\b401\b[^\n]*banned` ; `(?i)All connections banned` ; `(?i)connections? banned` ; existing auth_failed kept | s01, s02, s06 | `_AUTH_BANNED_PATTERNS` |
| FR-003 | `classify_abort` / `analyze_session` order: permanent **before** transient. Unit test: string matching both `API Error:` and `401` is permanent. | s01, s02 | as-built classify defaults transient |
| FR-004 | Audit `context_loop.py` / `run_session` retry: if `analysis.retryable` is False, **no** sleep+retry. If a second retry path ignores analysis — delete in-epic. | s03, s06 | loop halt |
| FR-005 | last-session.json records `abort_kind`, `retryable: false`, `need_human: true` (field names as-built schema; extra=forbid → use existing keys). Do not invent parallel marker file. | s03 | as-built keys: abort_kind + retryable; no need_human field |
| FR-006 | dirty_files collector: include globs under armed epic dir: `**/*.md`, `**/*.yaml`, `**/*.yml` relative to plan epic and implement/qa/bugfix dirs for epic_id. Exclude `__pycache__`, `.venv`. If collector currently hardcodes `md/plan.md` — delete that special case. | s04, s06 | yaml without sid in name |
| FR-007 | Tests in `harness/hooks/tests/` (session_resilience already has tests — extend, don't parallel module). | s01 | extend existing `loop/tests/test_session_*` (as-built home of classify tests) |
| FR-008 | Kind I comments «API Error always transient» — delete. | s02, s05, s06 | Kind I |
| FR-009 | DSH `_DSH_TRANSIENT_PATTERNS` must not reintroduce catch-all API Error. DSH permanent already has terminated/overloaded — keep; add 401/banned there too **or** share one pattern tuple (prefer shared constant `_AUTH_BANNED_PATTERNS` used by both). | s05, s06 | share tuple |
| FR-010 | UNKNOWN API Error (e.g. `API Error: weird`) after catch-all removal → retryable False (safe default). Optional: log metric `abort_unknown`. Not TRANSIENT. | s01, s02, s06 | fail-closed unknown |
| FR-011 | Do not change `DEFAULT_TRANSIENT_RETRY_MAX` as the fix for 401 (that's treating symptom). If audit finds a **second** retry max of 8/30 that ignores classifier — sunset that constant in-epic. | s02, s03 | symptom vs cause |
| FR-012 | KeyboardInterrupt remains FATAL, not retried. | s01, s02 | lock |
| FR-013 | Model substitution remains permanent (already). Regression test stays. | s01, s02 | lock |
| FR-014 | Independent Test is behavior of classify + loop halt, not «pattern exists in tuple». | s01, s03, s06 | anti-dilution |
| FR-015 | FRONT/INTEG loops share session_resilience — one fix. | s03, s05 | no per-role copy |
| US-001 | Как operator, 401 banned не ретраится. | s01, s02 | P0 classify |
| US-002 | Как DECOMPOSE session, All connections banned → NEED_HUMAN, не 8 пустых прогонов. | s03 | loop fixture |
| US-003 | Как implementer, timeout всё ещё retryable. | s01, s02 | lock transient |
| US-004 | Как resume, dirty yaml step виден без dirty plan.md. | s04 | dirty_files |
| US-005 | Как CI, catch-all API Error отсутствует в source. | s01, s02, s05, s06 | rg 0 |
| SC-001 | 401 banned not retryable | s01, s02 | pytest |
| SC-002 | catch-all gone | s01, s02, s05, s06 | rg + pytest |
| SC-003 | timeout still retryable | s01, s02 | pytest |
| SC-004 | dirty yaml listed | s04 | pytest tmp dirty |
| SC-005 | loop does not retry permanent | s03 | pytest/loop fixture |
| AC+1 | 401/banned → not TRANSIENT. | s01, s02, s06 | |
| AC+2 | Catch-all API Error deleted. | s02, s06 | |
| AC+3 | Transient list still covers timeouts/overload. | s01, s02 | |
| AC+4 | dirty_files includes yaml steps. | s04, s06 | |
| AC+5 | Loop honors retryable=False. | s03, s06 | |
| AC−1 | Нет catch-all `API Error:` в transient. | s01, s02, s05, s06 | |
| AC−2 | Нет «401 pattern after catch-all» dual. | s02, s06 | |
| AC−3 | Нет retry when retryable False. | s03, s06 | |
| AC−4 | Нет dirty_files = [plan.md] only. | s04, s06 | |
| AC−5 | Нет feature flag `RETRY_401` default on. | s02, s06 | |
| AC−6 | Нет второго classifier copy in context_loop that still catch-alls. | s03, s05, s06 | |
| NFR-1 | Halt 401 in one session, not N | s03, s06 | |
| NFR-2 | Classifier O(patterns × log size) unchanged order of magnitude | s02 | no ML; Appetite cut |
| NFR-3 | Kind I rg catch-all = 0 | s05, s06 | |
| TM-001 | P0 401 banned not retryable pytest classify retryable False | s01, s02 | US-001 FR-002 |
| TM-002 | P0 catch-all absent rg + pytest 0 hits | s01, s02, s06 | US-005 FR-001 |
| TM-003 | P0 timeout retryable pytest True | s01, s02 | US-003 |
| TM-004 | P0 dirty yaml listed pytest tmp path in list | s04 | US-004 FR-006 |
| TM-005 | P0 loop no retry permanent pytest loop one attempt | s03 | US-002 FR-004 |
| TM-006 | P1 All connections banned no API prefix pytest permanent | s01, s02 | FR-002 |
| TM-007 | P1 unknown API Error not transient pytest retryable False | s01, s02, s06 | FR-010 |
| TM-008 | P1 DSH 401 permanent pytest retryable False | s05 | FR-009 |
| Failure TM-001 | Catch-all leftover 401 retried | s01, s02, s06 | FAIL |
| Failure TM-002 | 401 not in permanent UNKNOWN retried if catch-all later | s01, s02 | US-001 |
| Failure TM-003 | Loop ignores retryable 8 empty sessions | s03 | |
| Failure TM-004 | dirty only plan.md yaml lost | s04 | |
| Failure TM-005 | timeout classified permanent lost retries | s01, s02 | |
| Failure TM-006 | DSH copy catch-all 401 on DSH retried | s05, s06 | |
| Failure TM-007 | unknown API Error transient storm | s02, s06 | FR-010 |
| Failure TM-008 | KeyboardInterrupt retried bad UX | s01, s02 | FR-012 |
| Independent Test PASS | 401 text → no retry; catch-all rg 0; dirty yaml listed; timeout still retries. | s01, s02, s03, s04, s06 | |
| Independent Test FAIL | «добавили 401 рядом с catch-all». | s02, s06 | dilution = FAIL ANALYZE |
| Product WHAT-1 | Abort classifier **не** ретраит auth/policy bans как TRANSIENT. `401` / `All connections banned` / org-banned API keys → `NEED_HUMAN` / `PERMANENT_FAILURE` / halt, **не** 8 пустых DECOMPOSE-циклов. | s01, s02, s03 | |
| Product WHAT-2 | Catch-all `API Error:[^\n]*` **удалить**. `dirty_files` на abort/resume включает yaml tree / steps / index, не только `plan.md`. | s02, s04, s06 | |
| Technology axiom Permanent abort | typed patterns: 401, banned, allowlist, auth | s02, s05 | FORBIDDEN catch-all as TRANSIENT |
| Technology axiom Transient abort | explicit list: timeout, overloaded, rate-limit, stream idle, connection reset | s01, s02 | FORBIDDEN any API Error is retryable |
| Technology axiom Unknown abort | UNKNOWN_FAILURE retryable=False | s02, s06 | better miss a retry than storm 401 |
| Technology axiom Dirty set | epic glob md+yaml under plan/implement | s04 | FORBIDDEN plan.md-only |
| Technology axiom Halt | NEED_HUMAN / PERMANENT_FAILURE in last-session | s03 | FORBIDDEN silent next DECOMPOSE spawn |
| Appetite cut ML classifier | out of scope | — | cut_list; no follow_up epic |
| Appetite cut rewrite all retry UX copy | out of scope | — | cut_list |
| Appetite cut Variant B event log | out of scope | — | cut_list |
| Out overlay 070 | Out: overlay (070) | — | follow_up: T-HUB-070-phase-policy-overlay-sole-sot (queue) |
| Out identity 071 | Out: identity (071) | — | follow_up: T-HUB-071-session-identity-lock (queue) |
| Out load_session 072 | Out: load_session (072) | — | follow_up: T-HUB-072-context-bundle-fail-closed (queue) |
| Out finish_qa 074 | Out: finish_qa (074) | — | follow_up: T-HUB-074-qa-bugfix-lifecycle-rearm (queue) |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| s01 — table-driven red tests 401/banned/timeout/catch-all presence | plan §До DECOMPOSE 1 | s01 |
| s02 — delete catch-all; add permanent patterns; shared tuple | plan §До DECOMPOSE 2 · Technology axiom | s02 |
| s03 — loop honor retryable=False (find second retry max if any) | plan §До DECOMPOSE 3 · FR-004/011 | s03 |
| s04 — dirty_files glob epic yaml+md | plan §До DECOMPOSE 4 · FR-006 | s04 |
| s05 — DSH parity + Kind I rg | plan §До DECOMPOSE 5 · FR-008/009 | s05 |
| s06 — purge leftover tests expecting catch-all | plan §До DECOMPOSE 6 · Replacement | s06 |
| Completeness ladder add → wire → enforce → purge | behavior-first §3 | s01 add; s02 add+enforce; s03 wire+enforce; s04 wire; s05 Kind I; s06 purge |
| Data flow stream → classify → loop → dirty → marker | plan §Data flow | s02, s03, s04 |
| Failure matrix 8 rows | plan §Failure matrix | s01–s06 (mapped per TM) |
| QA consumes test matrix TM-001…TM-008 | plan §qa-consumes | s01–s06 |
| Independent Test PASS/FAIL | plan §Independent Test | s01, s02, s03, s04, s06 |
| Eng spine classify → loop → dirty | plan §Eng spine | s02, s03, s04 |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| 401 / All connections banned / org-banned API keys не ретраятся; halt NEED_HUMAN, не 8 пустых DECOMPOSE | s01, s02, s03 |
| Catch-all `API Error:[^\n]*` удалён; dual «401 рядом с catch-all» запрещён | s01, s02, s06 |
| Timeout / overloaded / rate-limit / stream idle остаются retryable | s01, s02 |
| Unknown `API Error: weird` → UNKNOWN retryable False, не TRANSIENT | s01, s02, s06 |
| Loop / record_abort не spawn next session при retryable False; last-session abort_kind+retryable | s03, s06 |
| dirty_files включает yaml/steps и index, не только plan.md | s04, s06 |
| DSH 401 permanent; DSH transient без catch-all; Kind I comments gone | s05, s06 |
| NFR-1 Halt 401 in one session, not N | s03, s06 |
| NFR-2 Classifier O(patterns × log size) unchanged | s02 |
| NFR-3 Kind I rg catch-all = 0 | s05, s06 |
| KeyboardInterrupt FATAL; model substitution permanent (regression) | s01, s02 |
| Independent Test FAIL path («добавили 401 рядом с catch-all») | s02, s06 |
| Appetite cuts (ML / retry UX copy / Variant B event log) | — cut_list, не шаги |
| Overlay 070 / identity 071 / load_session 072 / finish_qa 074 | — follow_up queue |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Финальный `*-legacy-fallback-purge` в очереди с `sunset_inventory` + `grep_control`.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `_TRANSIENT_ABORT_PATTERNS` catch-all `API Error:[^\n]*` | A | explicit transient only | s02, s06 | no | FR-001; L110 sunset |
| missing 401/banned in permanent | A | `_AUTH_BANNED_PATTERNS` shared | s02, s05, s06 | no | FR-002/009 |
| dirty_files plan.md-only | A | epic glob md+yaml+yml | s04, s06 | no | FR-006 |
| any second retry ignoring analysis | A | honor retryable False | s03, s06 | no | FR-004 |
| tests asserting generic API Error is retryable True | A | rewrite UNKNOWN or specific transient | s01, s06 | no | FR-001 Kind I tests |
| n/a (same run_session / record-session) | B | same entrypoints | s06 | no | plan B n/a; inventory row |
| «retry unknown API Error» | C | UNKNOWN retryable False | s02, s06 | yes | FR-010; AC−5 no RETRY_401 |
| comments API Error always transient | I | permanent 401 | s05, s06 | no | FR-008 |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-abort-classifier-red-tests.yaml](../yaml/steps/s01-abort-classifier-red-tests.yaml) | [s01…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s01-abort-classifier-red-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-permanent-patterns-catch-all-delete.yaml](../yaml/steps/s02-permanent-patterns-catch-all-delete.yaml) | [s02…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s02-permanent-patterns-catch-all-delete.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-loop-honor-retryable-false.yaml](../yaml/steps/s03-loop-honor-retryable-false.yaml) | [s03…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s03-loop-honor-retryable-false.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-dirty-files-epic-yaml-glob.yaml](../yaml/steps/s04-dirty-files-epic-yaml-glob.yaml) | [s04…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s04-dirty-files-epic-yaml-glob.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-dsh-parity-kind-i.yaml](../yaml/steps/s05-dsh-parity-kind-i.yaml) | [s05…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s05-dsh-parity-kind-i.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-073-abort-classifier-dirty-halt/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-073-abort-classifier-dirty-halt` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
