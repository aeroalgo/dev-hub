# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-070-phase-policy-overlay-sole-sot  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3  
**Granularity:** 6 sNN (band 5–8; L3/L4 ≤9; advisory floor плана = 6; TDD red в s01; overlay delete+wire в s02; registry align в s03; stop-gate enforce в s04; Kind I rewrite в s05; apply≠purge → s06)

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-070-phase-policy-overlay-sole-sot/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add (red tests overlay OFF + REFLECT) → s02 wire (delete overlay policy; QA FINISH без REFLECT; projection = `gates_from_phase` only) → s03 add/wire (registry DECOMPOSE `need_verify: true` + `gates_from_phase` behavior) → s04 enforce (stop-gate honor need_verify; delete DECOMPOSE OFF special-case) → s05 Kind I (comments/tests/rg forbidden strings) → s06 purge leftovers A+B+C+I.  
> **Justification 6 sNN:** plan §До DECOMPOSE enumerates 6 outcomes; s02 overlay apply ≠ s03 registry value; s04 stop-gate enforce ≠ s02 hook emit; s05 Kind I rewrite ≠ s06 leftover inventory scan (apply≠purge).

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |
| `python-error-handling` | fail-closed unknown phase / stop-gate HALT |
| `python-configuration` | `phase_registry.yaml` DECOMPOSE gates |
| `python-type-safety` | `gates_from_phase` dict contract |

**Per-step:** BACK — skills gate в каждом `sNN` (`workflow-decompose.mdc`). Session skills (`writing-plans` / `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap-*.queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan.md`. Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Delete `armed_step=="DECOMPOSE"` override block in `user-prompt.py` (L159–172 as-built). No equivalent «docs-only» branch. | s01, s02, s06 | red then delete; leftover purge |
| FR-002 | Delete QA FINISH `→ REFLECT` string. Replace with registry-true next: QA → BUGFIX/DONE (prose may say `mb-finish qa`; **not** REFLECT). | s01, s02, s06 | pytest + rg |
| FR-003 | Align `phase_registry.yaml` DECOMPOSE `finish_gates` + `finish_gates_dict.need_verify: true`. Keep `need_reviewer: false`. Keep `verify_agent: verify-decompose`. | s03 | yaml + get_phase_config |
| FR-004 | `gates_from_phase("DECOMPOSE")` returns `need_verify: true` after change; tests on this function, not only yaml text. | s03 | behavior pytest TM-008 |
| FR-005 | Overlay when `projection_authoritative`: **only** apply `gates_from_phase`; never a second policy table in Python. | s02 | no DECOMPOSE if-table after projection |
| FR-006 | Regex path (`not projection_authoritative`) remains for IDE sessions without loop; **must not** mention REFLECT; **must not** special-case DECOMPOSE OFF. Drift: increment existing `gate_verdict_regex_fallback`-style counter if one exists, or add `overlay_regex_mode` diagnostic in spawn state (optional P1). | s02 | TM-005; regex stays, REFLECT/OFF gone |
| FR-007 | Kind I rewrite: any comment/test expecting DECOMPOSE verify OFF or QA→REFLECT — delete/rewrite in-epic. Search: `REFLECT обязател`, `verify/reviewer OFF`, `promote DECOMPOSE→IMPLEMENT`. | s05, s06 | TM-007 rg = 0 |
| FR-008 | spawn-hard.md already requires verify-decompose — **keep**. Do not weaken spawn-hard to match old overlay. | s05 | rg spawn-hard still ON |
| FR-009 | ANALYZE/IMPLEMENT promote remains `mb-finish decompose` / transition engine — overlay **не** promote. `promotable_after_finish: true` на DECOMPOSE в registry = prepare may promote **to ANALYZE** (canon), not IMPLEMENT. If prepare currently jumps IMPLEMENT, that is **074/transition leftover** — **out** unless one-line rg shows overlay-only. Confirm in DECOMPOSE: `finish_decompose` already ANALYZE (068/060). This epic does not rewrite `finish_decompose`. | s02 | overlay string deleted; `finish_decompose` **out_of_scope** (no follow-up rewrite) |
| FR-010 | Tests live under `harness/hooks/tests/` (user-prompt) and/or `loop/tests/` (registry). Independent Test = behavior of hook+registry, не «yaml field exists» alone (behavior-first §5). | s01, s03, s04 | named pytest files |
| FR-011 | Do not add a second `phase_policy.py` mega-module (Appetite: thin adapter). Max: small helper `overlay_gates(phase) -> dict` wrapping `gates_from_phase` if needed to avoid copy-paste. | s03 | NFR-2; unknown phase fail-closed TM-006 |
| FR-012 | FRONT/INTEG prefixes: overlay regex already role-agnostic; REFLECT/DECOMPOSE strings apply to all. Fix once. | s02 | one delete site |
| FR-013 | `POST_IMPLEMENT_CHAIN` / finish-block: if they still mention REFLECT as gate — Kind I in this epic **only** for hook overlay + tests that encode overlay. Broader workflow-qa REFLECT leftovers that 060 missed in **hooks** are in-scope; `.cursor/rules/**` rewrite only if shard later lists them — PLAN WHAT: overlay + registry + hook tests. Rules mention: if `rg` finds REFLECT as QA next in `user-prompt` comments only. | s04, s05 | stop-gate hook REFLECT in-scope; `.cursor/rules/**` Appetite cut |
| FR-014 | Stop-gate must honor DECOMPOSE need_verify after registry align. If stop-gate special-cases docs-only DECOMPOSE — delete that special case in this epic (wire-complete). | s04, s06 | TM-004 |
| FR-015 | No feature flag `PROJECT_LOOP_DECOMPOSE_VERIFY` default off. | s02, s03, s06 | AC−2 |
| US-001 | Как DECOMPOSE-агент, я хочу spawn-gate требовать `@verify-decompose`, а не OFF. | s01, s02, s04 | Independent Test: `need_verify is True`; context не содержит `verify/reviewer OFF` |
| US-002 | Как QA-агент, я не вижу «FINISH → REFLECT» после T-HUB-060. | s01, s02 | additionalContext не содержит `REFLECT` |
| US-003 | Как operator, я не хочу overlay promote DECOMPOSE→IMPLEMENT. | s02, s05 | context не содержит `promote DECOMPOSE→IMPLEMENT` |
| US-004 | Как CI, я хочу registry DECOMPOSE.need_verify == bool(verify_agent). | s03 | get_phase_config finish_gates_dict.need_verify is True |
| US-005 | Как loop, при armed projection regex не перебивает mode. | s02 | overlay не QA-ит armed; 071 identity halt follow_up |
| US-001 Given/When/Then | Given: epic loop env, `load_epic_state` armed_step=`DECOMPOSE`, projection.phase=`DECOMPOSE` / When: `user-prompt.main()` with prompt `BACK DECOMPOSE` / Then: `st["need_verify"] is True`; `st["need_reviewer"] is False`; additionalContext **не** match `verify/reviewer OFF`; **не** match `promote DECOMPOSE→IMPLEMENT` | s01, s02 | behavior cp |
| US-002 Given/When/Then | Given: `st["mode"]=="qa"` after projection or regex, prompt contains FINISH / When: UserPromptSubmit / Then: additionalContext may mention `@verify-qa` / reviewer / Handoff; **не** содержит `REFLECT` как обязательный next | s01, s02 | behavior cp |
| US-004 Given/When/Then | Given: `loop/schemas/phase_registry.yaml` after epic / When: `get_phase_config("DECOMPOSE")` / Then: `verify_agent == "verify-decompose"` AND `finish_gates_dict.need_verify is True` | s03 | pytest TM-003 |
| SC-001 | DECOMPOSE overlay need_verify true | s01, s02 | pytest hook |
| SC-002 | no REFLECT in QA FINISH inject | s01, s02, s06 | pytest + `rg` user-prompt.py |
| SC-003 | registry DECOMPOSE need_verify true | s03 | pytest get_phase_config |
| SC-004 | no DECOMPOSE→IMPLEMENT overlay string | s02, s05, s06 | `rg` user-prompt.py |
| SC-005 | stop-gate DECOMPOSE requires verify sidecar if need_verify | s04 | pytest or rg stop-gate |
| AC+1 | Overlay не выключает verify на DECOMPOSE. | s01, s02, s04 | Independent Test PASS path |
| AC+2 | Overlay не требует REFLECT после QA. | s01, s02 | |
| AC+3 | Registry DECOMPOSE.need_verify согласован с verify_agent. | s03 | |
| AC+4 | Тесты красные на старом override, зелёные на новом. | s01, s02 | TDD |
| AC+5 | Kind I: rg по запрещённым строкам в `harness/hooks/user-prompt.py` = 0. | s05, s06 | TM-007 |
| AC−1 | Нет dual policy: overlay vs registry на DECOMPOSE verify. | s02, s06 | ladder wire+purge |
| AC−2 | Нет soft flag default off для decompose verify. | s02, s03, s06 | FR-015 |
| AC−3 | Нет «preferred registry but overlay wins if armed». | s02, s06 | delete override, not wrap |
| AC−4 | Нет живых тестов, assert’ящих verify OFF на DECOMPOSE или QA→REFLECT. | s01, s05, s06 | obsolete tests rewrite |
| AC−5 | Нет второго Python таблицы фаз рядом с yaml. | s02, s03 | FR-011 |
| AC−6 | Misconfig registry (verify_agent set, need_verify false) → **этот эпик чинит**, не «документирует drift». | s03, s06 | axiom wedge |
| NFR-1 | Overlay policy table size → 0 special cases for DECOMPOSE/REFLECT | s02, s06 | rg no DECOMPOSE/REFLECT policy branch |
| NFR-2 | Hook still <200 LOC target (thin); no new framework | s02, s03 | wc -l user-prompt.py; no phase_policy.py |
| NFR-3 | Fail-closed: missing registry phase ≠ silent OFF | s03 | TM-006; gates_from_phase unknown ≠ default OFF |
| NFR-4 | Kind I rg = 0 hits on forbidden strings in user-prompt.py | s05, s06 | TM-007 |
| TM-001 | armed DECOMPOSE → need_verify true | s01, s02 | `bin/pytest harness/hooks/tests/test_user_prompt_overlay.py -q --tb=line -k decompose` |
| TM-002 | QA FINISH context without REFLECT | s01, s02 | pytest + rg |
| TM-003 | registry DECOMPOSE need_verify true | s03 | pytest get_phase_config |
| TM-004 | stop-gate respects need_verify DECOMPOSE | s04 | pytest stop-gate |
| TM-005 | regex FINISH QA no REFLECT | s02 | pytest FINISH_RE |
| TM-006 | unknown phase fail-closed | s03 | unit gates_from_phase / get_phase_config |
| TM-007 | Kind I rg user-prompt | s05, s06 | `rg -n 'REFLECT\|verify/reviewer OFF\|promote DECOMPOSE→IMPLEMENT' harness/hooks/user-prompt.py` expect 0 |
| TM-008 | gates_from_phase DECOMPOSE | s03 | need_verify true |
| Failure TM-001 | Overlay DECOMPOSE OFF leftover / verify skipped | s01, s02, s06 | pytest US-001 |
| Failure TM-002 | REFLECT string leftover / wrong next | s01, s02, s06 | pytest + rg |
| Failure TM-003 | registry need_verify false / gates_from_phase lies | s03, s06 | pytest SC-003 |
| Failure TM-004 | stop-gate ignores need_verify / docs-only FINISH | s04, s06 | pytest/rg |
| Failure TM-005 | regex path resurrect REFLECT / IDE session | s02, s06 | pytest FINISH_RE |
| Failure TM-006 | unknown phase / KeyError swallow | s03 | fail-closed diagnostic |
| Failure TM-007 | dual UserPromptSubmit (065) / double inject | — | follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint (note only) |
| Failure TM-008 | Kind I spawn-hard vs overlay / contradict | s05 | overlay deleted; spawn-hard kept ON |
| Independent Test PASS | hook DECOMPOSE need_verify true; QA inject без REFLECT; registry aligned; rg 0. | s01–s06 | named pytest + rg |
| Independent Test FAIL | «удалили комментарий» / «projection_authoritative уже есть» без удаления L164–172. | s02, s06 | dilution = FAIL ANALYZE |
| Technology axiom | Phase gates = `gates_from_phase(phase)` из `phase_registry.yaml`; QA next = registry + finish_qa BUGFIX/DONE; DECOMPOSE verify_agent set → need_verify true; Mode when armed = state/projection; Overlay text from registry **or** deleted. FORBIDDEN: hardcoded need_verify=False; `→ REFLECT`; docs-only OFF; QA_RE overlaps armed; второй командный канал прозой. Wedge: выровнять `finish_gates_dict.need_verify: true` + удалить overlay override. | s01–s06 | ladder add→wire→enforce→purge |
| Product WHAT 1 | После эпика UserPromptSubmit **не содержит** подстроки `REFLECT` как next после QA FINISH. | s02, s05, s06 | |
| Product WHAT 2 | При `armed_step=DECOMPOSE` spawn-gate `need_verify=true` (verify-decompose), `need_reviewer=false`; additionalContext **не** говорит verify OFF и **не** говорит promote IMPLEMENT. | s01, s02, s04 | |
| Product WHAT 3 | `phase_registry.yaml` DECOMPOSE: `finish_gates` / `finish_gates_dict.need_verify` согласованы с `verify_agent: verify-decompose` (true). | s03 | |
| Product WHAT 4 | Когда `projection.phase` или `state.armed_step` заданы — regex по prompt **не** меняет `st["mode"]` / gates (DECOMPOSE override — удалить). | s02 | |
| Product WHAT 5 | Kind I: spawn-hard, workflow-qa, любые hook comments — QA next ≠ REFLECT; DECOMPOSE verify ON. | s04, s05 | workflow-qa mdc outside hooks = Appetite cut |
| Product WHAT 6 | Тесты: fixture armed DECOMPOSE → need_verify true; fixture QA FINISH prompt → context без REFLECT; registry load DECOMPOSE need_verify true. | s01, s03 | |
| Appetite cut generate overlay from AST | `generate overlay from AST` | — | cut_list |
| Appetite cut Variant B event projector | `Variant B event projector` | — | cut_list; Eng review batch log |
| Appetite cut rewrite all workflow-qa mdc REFLECT | `rewrite all workflow-qa mdc REFLECT if any outside hooks` | — | cut_list; FR-013 |
| Out of scope | identity COMMAND lock (071) | — | follow_up: T-HUB-071-session-identity-lock |
| Out of scope | inline plan / `ok=true` (072) | — | follow_up: T-HUB-072-context-bundle-fail-closed |
| Out of scope | 401 classifier (073) | — | follow_up: T-HUB-073-abort-classifier-dirty-halt |
| Out of scope | finish_qa re-QA yaml (074, hard-deps этот эпик) | — | follow_up: T-HUB-074-qa-bugfix-lifecycle-rearm |
| Out of scope | duplicate realpath hooks (065) | — | follow_up: T-HUB-065-duplicate-hooks-runtime-entrypoint |
| Out of scope | sunset registry (063) | — | follow_up: T-HUB-063-sunset-boundary-stop-pipeline |
| Out of scope | fence ownership (066) | — | follow_up: T-HUB-066-boundary-schema-ownership-strict |
| Out of scope | rewrite `finish_decompose` / prepare jump IMPLEMENT leftover | — | FR-009: confirm ANALYZE only; no rewrite this epic |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| s01 — failing tests overlay DECOMPOSE OFF + REFLECT (TDD red) | plan §До DECOMPOSE #1 · FR-010 · US-001/002 · AC+4 · TM-001/002 | s01 |
| s02 — delete overlay blocks; QA FINISH prose without REFLECT | plan §До DECOMPOSE #2 · FR-001/002/005/006/012 · US-001–003/005 · AC+1/2 · Independent Test FAIL path | s02 |
| s03 — align phase_registry DECOMPOSE need_verify + gates_from_phase tests | plan §До DECOMPOSE #3 · FR-003/004/011 · US-004 · SC-003 · TM-003/006/008 · axiom wedge | s03 |
| s04 — stop-gate DECOMPOSE special-case purge | plan §До DECOMPOSE #4 · FR-014/013 · SC-005 · TM-004 · Failure TM-004 | s04 |
| s05 — Kind I rg + rewrite tests expecting old strings | plan §До DECOMPOSE #5 · FR-007/008/013 · AC+5 · TM-007 · sunset I | s05 |
| s06 — purge leftover comments / `legacy-fallback-purge` | plan §До DECOMPOSE #6 · Replacement A+B+C+I · AC−1–6 · Independent Test | s06 |
| Technology axiom lock | plan §Technology axiom | s01–s06 |
| Data flow stdin → state → registry → spawn-state → emit → stop-gate | plan §Eng review spine Data flow | s02–s04 |
| Add red tests (hook+registry behavior) | behavior-first ladder 1 Add | s01 |
| Wire overlay = gates_from_phase only | ladder 2 Wire | s02 |
| Wire registry need_verify true | ladder 1–2 Add/Wire | s03 |
| Enforce stop-gate DENY docs-only FINISH | ladder 3 Enforce | s04 |
| Kind I instruction rewrite | ladder 3 + Kind I | s05 |
| Purge leftover dual policy / REFLECT / OFF | ladder 4 Purge | s06 |
| QA consumes TM-001…TM-008 | plan §QA consumes | s01–s05 |
| Independent Test PASS/FAIL | plan §Independent Test | s01, s02, s06 |
| Product probe narrowest wedge | plan §Product probe #2 | s02, s03 |
| Pre-mortem overlay leftover if only registry aligned | plan §Product probe #3 | s02, s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Единственный machine SoT фазы и spawn-gates = `phase_registry.yaml` через `gates_from_phase` / `get_verify_agent` | s02, s03, s04 |
| UserPromptSubmit не пишет QA FINISH → REFLECT | s01, s02, s05, s06 |
| armed DECOMPOSE: need_verify true, need_reviewer false; нет verify OFF / promote IMPLEMENT | s01, s02, s04 |
| Registry DECOMPOSE.need_verify согласован с verify_agent (true) | s03 |
| Stop-gate не пропускает docs-only DECOMPOSE FINISH при need_verify | s04 |
| Kind I: 0 hits forbidden strings in user-prompt.py; spawn-hard не ослаблен | s05, s06 |
| Нет dual policy overlay vs registry; нет soft flag default off | s02, s03, s06 |
| Fail-closed unknown phase ≠ silent OFF | s03 |
| Thin hook (<200 LOC); нет mega `phase_policy.py` | s02, s03 |
| AC+ overlay не OFF / не REFLECT / registry aligned / TDD red-green / rg 0 | s01–s06 |
| AC− no dual policy · no soft flag · no overlay-wins-if-armed · no obsolete OFF tests · no second Python table · misconfig repaired in-epic | s02–s06 |
| Independent Test FAIL path (comment-only / projection_authoritative leftover) | s02, s06 |
| Out of scope (Appetite cut_list) | generate overlay from AST; Variant B event projector; rewrite all workflow-qa mdc outside hooks |
| Out of scope (follow-up queue) | 071 identity; 072 bundle; 073 classifier; 074 finish_qa; 065 duplicate hooks; 063 sunset; 066 fence |

## Replacement cleanup (plan → steps)

> Brownfield replace. Completeness ladder add → wire → enforce → purge. Финальный `s06-legacy-fallback-purge` с `sunset_inventory` + `grep_control` по каждой строке. Kind B plan = n/a (same UserPromptSubmit hook) — строка сохранена.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `user-prompt.py` DECOMPOSE armed override (`armed_step=="DECOMPOSE"` → `need_verify=False`, L159–172) | A | `gates_from_phase` only | s02, s06 | no | FR-001; Independent Test FAIL if only comment deleted |
| `user-prompt.py` REFLECT QA FINISH sentence (`Handoff → REFLECT.`) | A | QA FINISH → reviewer + `mb-finish qa` (no REFLECT) | s02, s06 | no | FR-002 |
| `phase_registry.yaml` DECOMPOSE `need_verify: false` (finish_gates / finish_gates_dict) | A | `true` (keep need_reviewer false, verify_agent verify-decompose) | s03, s06 | no | axiom wedge |
| tests expecting OFF/REFLECT overlay | A | rewrite on new contract | s01, s05, s06 | no | AC−4 |
| `stop-gate.py` `armed_step_u == "DECOMPOSE": st["need_verify"] = False` | A | honor registry/spawn `need_verify`; keep verify-decompose VERDICT check | s04, s06 | no | FR-014 |
| n/a (same UserPromptSubmit hook) | B | — | s06 | no | plan B n/a; inventory row for completeness |
| «docs-only DECOMPOSE» overlay/stop-gate | C | verify-decompose required | s02, s04, s06 | yes | delete in-epic |
| overlay wins if registry missing (silent default_gates OFF) | C | fail-closed unknown phase | s03, s06 | yes | NFR-3 TM-006 |
| overlay `QA FINISH → REFLECT` instruction | I | DONE/BUGFIX / mb-finish qa | s02, s05, s06 | no | |
| overlay `verify OFF` + `promote IMPLEMENT` | I | verify-decompose ON; next ANALYZE via mb-finish | s02, s05, s06 | no | |
| comments in user-prompt.py teaching OFF/REFLECT | I | registry comment | s02, s05, s06 | no | |
| stop-gate QA FINISH messages `pass → Handoff BACK REFLECT` | I | pass → DONE / mb-finish qa; blocked → BUGFIX | s04, s05, s06 | no | FR-013 hooks in-scope |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-overlay-red-tests.yaml](../yaml/steps/s01-overlay-red-tests.yaml) | [s01…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s01-overlay-red-tests.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s02** | [s02-delete-overlay-policy.yaml](../yaml/steps/s02-delete-overlay-policy.yaml) | [s02…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s02-delete-overlay-policy.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s03** | [s03-registry-need-verify-align.yaml](../yaml/steps/s03-registry-need-verify-align.yaml) | [s03…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s03-registry-need-verify-align.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-stop-gate-decompose-enforce.yaml](../yaml/steps/s04-stop-gate-decompose-enforce.yaml) | [s04…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s04-stop-gate-decompose-enforce.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-kind-i-overlay-rewrite.yaml](../yaml/steps/s05-kind-i-overlay-rewrite.yaml) | [s05…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s05-kind-i-overlay-rewrite.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-legacy-fallback-purge.yaml](../yaml/steps/s06-legacy-fallback-purge.yaml) | [s06…](../../implement/T-HUB-070-phase-policy-overlay-sole-sot/s06-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | pending |

**needs_creative:** все `no` (plan: CREATIVE need нет).

**Next after DECOMPOSE FINISH:** `BACK ANALYZE T-HUB-070-phase-policy-overlay-sole-sot` only. **FORBIDDEN** ANALYZE deferred → IMPLEMENT.
