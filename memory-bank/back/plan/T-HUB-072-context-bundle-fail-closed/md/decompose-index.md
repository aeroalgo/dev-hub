# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-072-context-bundle-fail-closed  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red в s01; add classifier+ok в s02; wire SessionStart path-only в s03; exception enforce в s04; Kind I + yaml inline в s05; apply≠purge → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-072-context-bundle-fail-closed/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests missing ok + plan inline) → s02 add (`is_markdown_plan_path` + empty content + fail-closed ok) → s03 wire (`session_start_payload` path+sha; never inline plan.md) → s04 enforce (exception incomplete, no Warning continue) → s05 Kind I + yaml still inline → s06 leftover inventory scan (apply≠purge).  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s02 classifier/ok ≠ s03 SessionStart renderer; s04 exception path is independent Kind C outcome; s05 Kind I rewrite ≠ s06 leftover inventory; yaml-inline is product FR (US-003) not a micro-ladder of s02.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | fail-closed missing / exception incomplete |
| `python-type-safety` | MbLoadFile extra=forbid — empty content + diagnostic, не новый field без schema |

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap/queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | After the per-path loop, `ok_status = False` if any missing_file/read_error. Remove unconditional `ok_status = True` at L97. Combine with plan_section errors. | s01, s02, s06 | as-built already `derived_ok`; purge leftover True |
| FR-002 | Classifier `is_markdown_plan_path(path)` : `md/plan.md` suffix, `plan-*.md` under memory-bank, gap-*.md optional same policy (architecture: plan/gap not inline). | s02, s03 | nouns: is_markdown_plan_path |
| FR-003 | For those paths: store sha256+size; `content=""` or omit from inject renderer; `truncated=False`; maybe `kind=path_ref` if schema allows extra field — **if extra=forbid** on MbLoadFile, use empty content + diagnostic `path_only:plan.md` **without** failing ok (file exists). Existence still required. | s01, s02, s03 | extra=forbid → empty content |
| FR-004 | SessionStart renderer uses files.content only if non-empty; always lists paths. | s03, s05 | inject manifest |
| FR-005 | `load_plan_section` not called from SessionStart hot path. If CLI still has flag — keep but SessionStart does not pass plan_section. | s03, s06 | TM-006; CLI keep |
| FR-006 | Cap: yaml overflow still truncated flag; required yaml truncated → ok false **or** documented ok true with truncated (choose: **ok false if truncated required yaml** to fail-closed — may be strict; Appetite: truncated yaml ok=true with truncated=true as today, **missing** not ok). Decision: **missing/read_error → ok false**; truncate → keep truncated flag, ok true (avoid blocking huge yaml). Plan md never truncated because not inlined. | s02, s05 | locked decision: truncate ok true |
| FR-007 | Kind I: docs saying load_now bodies always inlined — rewrite. | s05, s06 | sunset I |
| FR-008 | Tests in `loop/tests/` for load_session. | s01, s02 | test_mb_load_session.py |
| FR-009 | Do not inline `decompose-index.md` (md coverage) — path-only same as plan. yaml index **may** inline (small). | s02, s03, s05 | TM-007 |
| FR-010 | forbidden_skipped from resolver still ok if policy skip; missing **required resolved** path not skipped → not ok. | s02 | as-built resolver |
| FR-011 | SessionStart catch Exception: set inject warning **and** treat as incomplete (do not look like full success). Exact hook code as-built — find `load_session exception` and fail-closed. | s04, s06 | sunset C |
| FR-012 | Graphify N/A hub — n/a. | — | n/a hub; no sNN; documented in s02 out_of_scope |
| US-001 | Как DECOMPOSE, я не получаю тело plan.md в SessionStart. | s01, s03 | Independent Test inject |
| US-002 | Как runner, missing required file → ok false. | s01, s02 | pytest load_session |
| US-003 | Как IMPLEMENT, yaml shard всё ещё может быть inline. | s03, s05 | content present if < cap |
| US-004 | Как агент, sha256 plan доступен чтобы заметить drift. | s01, s02, s03 | sha len 64 |
| US-005 | Как SessionStart, exception load_session не silent success. | s04 | hook diagnostic |
| SC-001 | missing → ok false | s01, s02 | pytest |
| SC-002 | plan.md not in inject body | s01, s03 | pytest |
| SC-003 | yaml still inline | s03, s05 | pytest |
| SC-004 | sha present for path-only | s01, s02, s03 | pytest |
| SC-005 | SessionStart exception not silent ok | s04 | pytest/hook |
| AC+1 | ok=false on missing required. | s01, s02, s06 | |
| AC+2 | plan.md path-only in SessionStart. | s01, s03, s06 | |
| AC+3 | yaml inline remains. | s03, s05 | |
| AC+4 | Independent tests as behavior. | s01, s03, s04 | |
| AC−1 | Нет ok=true при missing_file. | s01, s02, s06 | |
| AC−2 | Нет «inline plan if < 256KiB». | s01, s03, s06 | |
| AC−3 | Нет heading-split SoT on start. | s03, s06 | FR-005 |
| AC−4 | Нет silent exception continue as success. | s04, s06 | |
| AC−5 | Нет dual loader (old inline + new path) both emitting body. | s03, s05, s06 | |
| NFR-1 | SessionStart context size not dominated by plan.md | s03, s05 | path-only |
| NFR-2 | Completeness honest | s02, s04, s06 | ok false / incomplete |
| NFR-3 | Hash cheap (read file once) | s02 | sha of full bytes once |
| TM-001 | P0 missing file pytest load_session ok false | s01, s02 | US-002 |
| TM-002 | P0 plan.md no body pytest content empty in inject | s01, s03 | US-001 |
| TM-003 | P0 yaml inline pytest content present | s03, s05 | US-003 |
| TM-004 | P1 sha path-only pytest sha256 len 64 | s01, s02, s03 | US-004 |
| TM-005 | P0 exception incomplete pytest hook not success | s04, s06 | US-005 |
| TM-006 | P1 no plan_section on start rg 0 call | s03, s06 | FR-005 |
| TM-007 | P1 index.md path-only pytest | s02, s05 | FR-009 |
| TM-008 | P1 read_error ok false pytest | s01, s02 | FR-001 |
| Failure TM-001 | missing file ok true | s01, s02, s06 | ok false |
| Failure TM-002 | plan inline | s01, s03, s06 | path-only |
| Failure TM-003 | yaml missing | s02 | same as missing |
| Failure TM-004 | truncate yaml | s02, s05 | ok true + flag |
| Failure TM-005 | exception swallow | s04, s06 | incomplete |
| Failure TM-006 | load_plan_section start | s03, s06 | not called |
| Failure TM-007 | index.md inline | s02, s05 | path-only |
| Failure TM-008 | sha mismatch later | s02 | fingerprint; follow_up 071 |
| Independent Test PASS | missing → not ok; plan.md body absent from inject; yaml present. | s01, s03, s05 | |
| Independent Test FAIL | «cap 256KiB enough so inline OK». | s01, s03, s06 | dilution = FAIL ANALYZE |
| Product WHAT-1 | `load_session`: if any `missing_file:` or `read_error:` on **required** load_now paths → `ok=False`. | s01, s02 | |
| Product WHAT-2 | Policy: all load_now paths from AC are required unless marked optional (today none optional → all required). | s02 | optional parser as-built |
| Product WHAT-3 | Files matching `**/md/plan.md` or `plan-*.md` monolith: `MbLoadFile.content` empty or omitted; `sha256` of full file still computed. | s02, s03 | |
| Product WHAT-4 | SessionStart additionalContext for md plan: `path + sha256 + size`, instruction «Read this path»; not the body. | s03 | |
| Product WHAT-5 | yaml steps / qa yaml: may still inline under cap. Rule: **markdown plan/gap** path-only; **yaml/json** inline if ≤ cap. | s03, s05 | |
| Product WHAT-6 | Tests: missing file → ok false; plan.md fixture 400 lines → inject has no `# Heading` body from plan. | s01, s03 | |
| Technology axiom Bundle completeness | `MbLoadResult.ok` false if required missing | s02 | FORBIDDEN ok=true + missing_file |
| Technology axiom Markdown plan | path_ref + sha256, `inline_body=false` | s02, s03 | FORBIDDEN full plan.md in additionalContext |
| Technology axiom yaml/json | inline ≤ cap only if inline=true policy | s02, s05 | truncated may ok with flag |
| Technology axiom plan sections | yaml anchors / not SoT | s03 | FORBIDDEN `load_plan_section` `##` as COMMAND/AC |
| Technology axiom SessionStart exception | fail-closed diagnostic | s04 | FORBIDDEN Warning continue as success |
| Out of scope | LoadNowItem.kind enum rollout | — | Appetite cut_list |
| Out of scope | sunset forbidden_for_parent consume (063) | — | follow_up: T-HUB-063-sunset-boundary-stop-pipeline |
| Out of scope | plan yaml section offsets | — | Appetite cut_list |
| Out of scope | identity COMMAND | — | follow_up: T-HUB-071-session-identity-lock |
| Out of scope | overlay REFLECT/verify OFF | — | follow_up: T-HUB-070-phase-policy-overlay-sole-sot |
| Out of scope | abort 401 / dirty halt | — | follow_up: T-HUB-073-abort-classifier-dirty-halt |
| Out of scope | QA/BUGFIX finish_qa rearm | — | follow_up: T-HUB-074-qa-bugfix-lifecycle-rearm |
| Out of scope | JSON session contract | — | follow_up: T-HUB-057-loop-session-json-contract |
| Out of scope | Graphify N/A hub | — | FR-012 n/a |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| s01 — red tests missing ok + plan inline | plan §До DECOMPOSE 1 | s01 |
| s02 — load_session ok_status fix + classifier | plan §До DECOMPOSE 2 · Wire-complete Add | s02 |
| s03 — path-only classifier + inject renderer | plan §До DECOMPOSE 3 · Wire-complete Wire | s03 |
| s04 — SessionStart exception path | plan §До DECOMPOSE 4 · sunset C | s04 |
| s05 — Kind I + yaml still inline tests | plan §До DECOMPOSE 5 · FR-007/US-003 | s05 |
| s06 — purge | plan §До DECOMPOSE 6 · Wire-complete Purge | s06 |
| Data flow AC → resolve → read/missing → kind → MbLoadResult → additionalContext | plan §Data flow | s02, s03 |
| Failure matrix 8 rows | plan §Failure matrix | s01–s06 (mapped per TM) |
| Path classifier table (plan.md never / yaml yes) | plan §Path classifier | s02, s05 |
| Wire-complete add→wire→enforce→purge | plan §Wire-complete · behavior-first §3 | s01–s06 |
| Independent Test PASS/FAIL | plan §Independent Test | s01, s03, s05, s06 |
| QA consumes load_session + session-start inject | plan §QA consumes | s01–s06 tests |

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Completeness честный: missing/read_error required → ok false, не partial success | s01, s02, s06 |
| Markdown plan в load_now = path + sha; тело не в SessionStart | s01, s02, s03 |
| Агент читает plan через Read, не через ложный «файл уже в контексте» | s03, s05 |
| yaml shard IMPLEMENT всё ещё inline под cap | s03, s05 |
| sha256 plan доступен для drift | s02, s03 |
| SessionStart exception → incomplete HALT, не Warning continue | s04, s06 |
| decompose-index.md / gap / analyze md path-only | s02, s05 |
| SessionStart context size not dominated by plan.md | s03, s05 |
| Kind I «load_now always inlined» gone | s05, s06 |
| heading-split load_plan_section not start SoT | s03, s06 |
| Independent Test FAIL path («cap 256KiB enough so inline OK») | s01, s03, s06 |
| Wire-complete sole SoT | s01–s06 |
| Out of scope (не в этой нарезке) | — / follow-up 063/057/070/071/073/074 + Appetite cut |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** `roadmap/queue.yaml`).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Greenfield → n/a. Здесь brownfield: inline plan.md + leftover ok_status True + Warning continue.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `ok_status = True` after missing continue (`session.py` old L97) | A | `derived_ok` False if any missing_file/read_error | s02, s06 | no | FR-001; as-built may already be derived_ok — leftover True must die |
| inline plan.md content in `MbLoadFile.content` / additionalContext | A | path+sha empty content | s02, s03, s06 | no | FR-003/004 |
| SessionStart `load_plan_section` / `plan_section=` call | A | `load_session(cwd)` only | s03, s06 | no | FR-005; CLI flag may remain |
| tests asserting plan.md body in additionalContext as success | A | rewrite path-only asserts | s01, s05, s06 | no | obsolete tests |
| n/a (same mb-load session CLI / SessionStart hook) | B | same entrypoints | s06 | no | plan B n/a; inventory row |
| Warning continue exception as success | C | CONTEXT_INCOMPLETE `required_context_exception` | s04, s06 | yes | AC−4; FR-011 |
| «inline plan if < 256KiB» dual path | C | never inline classifier md regardless size | s03, s06 | yes | AC−2 |
| docs / comments «load_now files inlined» | I | path-only for md plan/gap/index | s05, s06 | no | FR-007 |
| instructions teaching heading-split `load_plan_section` as SessionStart SoT | I | path-only; CLI may keep flag | s03, s05, s06 | no | Technology axiom plan sections |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-bundle-red-tests.yaml](../yaml/steps/s01-bundle-red-tests.yaml) | [s01…](../../implement/T-HUB-072-context-bundle-fail-closed/s01-bundle-red-tests.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-path-only-classifier.yaml](../yaml/steps/s02-path-only-classifier.yaml) | [s02…](../../implement/T-HUB-072-context-bundle-fail-closed/s02-path-only-classifier.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-session-start-path-only-wire.yaml](../yaml/steps/s03-session-start-path-only-wire.yaml) | [s03…](../../implement/T-HUB-072-context-bundle-fail-closed/s03-session-start-path-only-wire.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-session-start-exception-enforce.yaml](../yaml/steps/s04-session-start-exception-enforce.yaml) | [s04…](../../implement/T-HUB-072-context-bundle-fail-closed/s04-session-start-exception-enforce.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-kind-i-yaml-inline.yaml](../yaml/steps/s05-kind-i-yaml-inline.yaml) | [s05…](../../implement/T-HUB-072-context-bundle-fail-closed/s05-kind-i-yaml-inline.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-072-context-bundle-fail-closed/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-072-context-bundle-fail-closed` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
