# Реестр шагов (Decompose index)

**Plan ID:** T-HUB-067-pack-doctor-executable-graph  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-06  
**Режим:** BACK DECOMPOSE  
**Уровень:** L3–L4  
**Granularity:** 5 sNN (band 5–8; advisory floor плана = 7; red fixtures + `check_pack_graph` + compose 062/064 + doctor CLI слиты в s01 — один operator outcome `ok=false` + precise codes на unusable pack; Kind I + software/video report слиты в s04; apply ≠ purge → s05 отдельно). Justification: micro-ladder schema→CLI→wire запрещён; doctor CLI = invoke того же graph, не отдельный outcome.

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — `.cursor/templates/decompose/epic-step.yaml`.

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-067-pack-doctor-executable-graph/md/decompose-index.md`. Machine = `yaml/decompose-index.yaml`. Shards = `yaml/steps/`.  
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `decompose-index.yaml` only.**  
> **Ladder:** s01 add+enforce pack graph (Path.exists + declare + skill_refs compose + doctor exit≠0) → s02 add+enforce load_session derived ok → s03 wire SessionStart CONTEXT_INCOMPLETE + exception split → s04 Kind I + software regression / video report → s05 purge leftover ok=true + Warning-as-success.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE, не `impl:`) |
| `tdd` / `python-testing-patterns` / `modern-python` / `python-anti-patterns` | Core(4) в каждом code sNN |

**Per-step:** skills gate в каждом `sNN` (`skills-gate-situational.mdc`). Session skills (`writing-plans`, `brainstorming`) **FORBIDDEN** в `impl:`.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR / US / SC → ≥1 шаг, иначе `out_of_scope` + `follow_up:` уже в `memory-bank/back/roadmap/queue.yaml`.  
> Колонка **Plan FR text** = дословно из `plan.md`. Covered row ⇒ measurable `verify` (не map-only).

| Req ID | Plan FR text (verbatim) | sNN | Notes / measurable verify |
| :--- | :--- | :--- | :--- |
| FR-001 | `check_pack_graph(pack)` walks: registry entry, `rules_root` exists, each role index, each intent→route Path.exists, each `_lean` gate referenced by workflow Gates, each phase `verify_agent` in manifest **or** `no_gate_reason`, each schema_id in BOUNDARY_REGISTRY if pack declares schemas. | s01 | pytest fixture missing route/gate/agent → codes; walk not keys-only |
| FR-002 | Precise fail codes (axiom table). Multiple codes allowed (list), not first-only hide. | s01 | axiom: `pack_route_missing` · `pack_gate_missing` · `pack_agent_missing` · `skill_ref_missing` · `pack_schema_missing`; list, not first-only |
| FR-003 | Consume 062 skill checker on pack/workflow corpora (or call same function). Missing skill → `skill_ref_missing` counts as pack unusable if referenced from pack rules. | s01 | call `check_skill_refs` / `skill_refs.py`; no fork |
| FR-004 | Consume 064 route exists helper; do not duplicate divergent exists logic. | s01 | reuse `route_command` / `pack_route_missing`; `rg` 0 second exists-implementation |
| FR-005 | Doctor CLI exit ≠0 when any registered pack unusable; `--pack` filter. | s01 | `run_doctor_workflow_pack` / `loop doctor --check workflow-pack` exit 1 + `--pack` |
| FR-006 | `load_session`: never set `ok=True` after required miss/read error. Derive `ok = not required_missing and not read_errors_on_required`. | s02 | unit: missing required → `ok is False` |
| FR-007 | Request model: entries marked required vs optional. Unmarked = required (fail-closed). | s02 | unmarked required; optional miss → ok true |
| FR-008 | Result schema fields: `required_missing`, `optional_missing`, `forbidden_skipped`, `fingerprint`, `status=complete\|incomplete`. | s02 | fields on `MbLoadResult` |
| FR-009 | SessionStart: if `status=incomplete` or `ok=false` → inject `CONTEXT_INCOMPLETE` + codes; **forbid** presenting leftover files as sufficient for main work. Halt vs degrade: halt when **any required** missing; degrade documented only for optional. | s03 | hook unit: no success inject of leftover required |
| FR-010 | Split diagnostic-only exceptions vs required-context exceptions (audit 03 §4). Required → typed code, not `Warning: load_session exception`. | s03 | `rg` 0 `Warning: load_session exception` as success path for required |
| FR-011 | pytest fixtures: (a) missing route (b) missing gate (c) missing agent (d) missing required load path (e) optional missing still ok=true. | s01, s02 | five fixtures named in tdd |
| FR-012 | Kind I: pack README / CLAUDE pack table cannot say «fully wired» while doctor red. | s04 | docs honest after doctor |
| FR-013 | Software pack regression: doctor green on `dev-hub-software` after 064 video leftover — video pack may stay red until 064; doctor must still **report** video red, not skip pack. | s04 | doctor reports video; software exists-based green |
| FR-014 | Do not swallow doctor IO errors as skip pack. | s01 | IO → `workflow_pack_check_error` / listed codes, not skip |
| FR-015 | External tool gates (ffmpeg) = `pack_tool_gate_missing` **advisory vs fail**: Appetite cut = fail only if pack `tool_gates.required=true`; video ffmpeg remains 051 — this epic documents field, default not fail hub software pack. | s01 | field documented; software not fail on ffmpeg; follow_up T-HUB-051 |
| US-001 | Как CI, я хочу doctor red на missing workflow route. | s01 | fixture pack → `pack_route_missing` |
| US-002 | Как CI, я хочу doctor red на phase verify_agent not in manifest. | s01 | `pack_agent_missing` |
| US-003 | Как CI, я хочу doctor red на missing `_lean` gate file. | s01 | `pack_gate_missing` |
| US-004 | Как operator, я не хочу SessionStart с ok=true при дырявом load_now. | s02, s03 | load_session missing required → ok=false; SessionStart halt |
| US-005 | Как parent, я хочу явный CONTEXT_INCOMPLETE вместо Warning. | s03 | session_start_payload missing file → halt/degrade code |
| SC-001 | broken route fixture code exact | s01 | pytest pack graph |
| SC-002 | load required miss → ok false | s02 | unit |
| SC-003 | SessionStart incomplete not success inject | s03 | hook/unit |
| SC-004 | software pack doctor uses exists not keys-only | s01, s04 | pytest + doctor --pack |
| SC-005 | optional miss → ok true + optional_missing | s02 | unit |
| AC+1 | Doctor fail-closed on unusable pack with precise codes. | s01 | exit≠0 + codes list |
| AC+2 | load_session ok iff required complete. | s02 | derived ok |
| AC+3 | SessionStart does not treat partial required as success. | s03 | CONTEXT_INCOMPLETE |
| AC+4 | Optional typed and does not flip ok. | s02 | optional_missing |
| AC+5 | Skill/route checkers composed, not forked. | s01 | 062+064 reuse |
| AC−1 | Нет `ok=true` + `missing_file` on required. | s02, s05 | derive; purge leftover |
| AC−2 | Нет doctor green on yaml-only keys. | s01, s05 | Path.exists walk |
| AC−3 | Нет Warning-only on required context exception. | s03, s05 | typed halt |
| AC−4 | Нет skip video pack in doctor because red. | s04, s05 | report TM-008 |
| AC−5 | Нет second exists-implementation diverging from 064. | s01, s05 | compose route_command |
| TM-001 (QA) | missing route fixture → pack_route_missing | s01 | QA table maps US-001 |
| TM-002 (QA) | missing gate fixture → pack_gate_missing | s01 | QA maps US-003 |
| TM-003 (QA) | missing agent fixture → pack_agent_missing | s01 | QA maps US-002 |
| TM-004 (QA) | required load miss → ok false | s02 | QA maps US-004 |
| TM-005 (QA) | SessionStart incomplete → CONTEXT_INCOMPLETE | s03 | QA maps US-005 |
| TM-006 (QA) | optional miss → ok true + optional_missing | s02 | QA maps FR-007 |
| TM-007 (QA) | software pack exists-based | s04 | QA maps FR-013 |
| Failure matrix TM-001 | missing route → pack_route_missing | s01 | spine TM-001 (same as QA TM-001) |
| Failure matrix TM-002 | missing gate → pack_gate_missing | s01 | spine ≠ QA TM-002 numbering for load — keep spine IDs here |
| Failure matrix TM-003 | undeclared verify agent → pack_agent_missing | s01 | |
| Failure matrix TM-004 | missing skill @ → skill_ref_missing | s01 | |
| Failure matrix TM-005 | required load miss → ok false | s02 | spine TM-005 = QA TM-004 |
| Failure matrix TM-006 | optional miss → ok true | s02 | spine TM-006 = QA TM-006 |
| Failure matrix TM-007 | exception swallow → typed halt | s03 | |
| Failure matrix TM-008 | doctor skips red pack → report | s04 | |
| Failure matrix TM-009 | keys-only doctor → fail exists | s01 | |
| Independent Test PASS | fixture missing route → exact code; required miss → ok false; optional miss → ok true. | s01, s02 | named pytest |
| Independent Test FAIL | «doctor prints yaml keys» without Path.exists; «diagnostic_codes nonempty but ok true» as accepted. | s01–s05 | dilution = FAIL ANALYZE |
| Technology axiom | Pack usable = every route Path.exists + every verify_agent declared; Doctor codes axiom table; load_session ok=true iff required complete; SessionStart required_missing → CONTEXT_INCOMPLETE; Optional files typed `optional=true` | s01–s05 | ladder add→wire→enforce→purge |
| Out of scope | template pack authoring | — | Appetite `cut_list` |
| Out of scope | MCP load rewrite | — | Appetite cut_list |
| Out of scope | full ContextBoundaryService class | — | Appetite `cut_list`; follow_up: T-HUB-068-start-finish-transaction-boundary |
| Out of scope | ffmpeg required gate | — | Appetite `cut_list`; follow_up leftover T-HUB-051; FR-015 documents advisory field only |
| NFR | n/a — plan has no numbered NFR table | — | Goal/NFR preserved in Outcome map (doctor honesty + fail-closed) |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| red tests: route/gate/agent fixtures + load ok false | plan §До DECOMPOSE #1 · FR-011 (a)(b)(c) | s01 (route/gate/agent) + s02 (load ok false) — TDD red живёт в owner step, не отдельный sNN |
| `check_pack_graph` exists+codes; doctor CLI | plan §До DECOMPOSE #2 · FR-001/002/005 | s01 (слито с red fixtures — один Path.exists + codes outcome) |
| compose skill_refs (062) | plan §До DECOMPOSE #3 · FR-003/004 | s01 (не micro-split compose vs walk — same graph function) |
| load_session derive ok + result fields | plan §До DECOMPOSE #4 · FR-006/007/008 | s02 |
| SessionStart CONTEXT_INCOMPLETE + exception split | plan §До DECOMPOSE #5 · FR-009/010 | s03 |
| Kind I docs; software pack assertion | plan §До DECOMPOSE #6 · FR-012/013 | s04 |
| purge ok=true leftover + Warning-as-success | plan §До DECOMPOSE #7 · Replacement A+C | s05 |
| Add → Wire → Enforce → Purge | workflow-behavior-first §3 | s01 add+enforce graph · s02 derive ok · s03 wire SessionStart · s04 Kind I · s05 purge |
| Data flow: pack registry → check_pack_graph → codes[]; SessionStart → load_session → CONTEXT_INCOMPLETE | plan §Eng review spine | s01, s02, s03 |
| Failure matrix TM-001…009 | plan §Failure matrix · §QA consumes | s01–s05 |
| Product WHAT #1–5 | plan §Продуктовая спека | s01 (1–2) · s02 (3) · s03 (4–5) |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Pack `ok=true` только если **исполняемый граф** цел (routes, gates, agents, schemas, skills) | s01 |
| Broken fixture packs fail with **precise** codes (not generic ok=false) | s01 |
| Doctor CLI exit ≠0 on unusable pack; `--pack` filter; IO not skip | s01 |
| CI red on missing route / undeclared verify_agent / missing `_lean` gate | s01 |
| `load_session` `ok=true` iff все required `load_now` прочитаны | s02 |
| Result machine fields `required_missing` / `optional_missing` / `forbidden_skipped` / `status` | s02 |
| Optional miss does not flip ok | s02 |
| SessionStart не inject-ит partial required bundle как normal context | s03 |
| Required exception → typed CONTEXT_INCOMPLETE, не Warning-as-success | s03 |
| Partial bundle fingerprint `status=incomplete` | s02, s03 |
| Docs не врут «pack wired» / «partial load ok» пока doctor/load red | s04 |
| Software pack doctor exists-based green; video red **reported**, not skipped | s04 |
| Leftover `ok=true` after required miss / keys-only doctor / Warning swallow purged | s05 |
| Independent Test PASS: missing route exact code; required miss ok false; optional miss ok true | s01 + s02 |
| Independent Test FAIL dilution: yaml keys without Path.exists; diagnostic_codes nonempty but ok true | s01–s05 (не done) |
| Appetite cuts (template UI / MCP rewrite / ContextBoundaryService / ffmpeg required) | — follow_up IDs |
| Goal: executable graph honesty for operator/CI | s01–s05 (не infra-only titles) |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN` с непустым `deletes:` (или OOS + follow-up в queue).  
> Completeness ladder: **add → wire → enforce → purge**. Add-only на sole-path FR = FAIL (`optional_sot`).  
> Финальный `s05-legacy-fallback-purge` с `sunset_inventory` + `grep_control` по каждой строке.

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `ok=true` after required miss (`ok_status = True` after `missing_file:`) | A | derived `ok = not required_missing and not read_errors_on_required` | s02 (apply), s05 (leftover) | no | `loop/mb_load/session.py` L64/L97 |
| pack resolve / doctor without per-route Path.exists (`full_resolve`/`check_workflow_pack` keys-only: rules_root dir + phase_registry file) | A | `check_pack_graph` exists+declare | s01, s05 | no | delete in-epic |
| doctor keys-only (yaml keys present, file missing → green) | A | exists+declare walk | s01, s05 | no | Independent Test FAIL pattern |
| tests asserting `ok=True` with nonempty `missing_file:` on required | A | rewrite asserts | s02, s05 | no | obsolete contract |
| doctor exit 0 on unusable pack | B | exit ≠0; `--pack` filter | s01, s05 | no | `run_doctor_workflow_pack` |
| SessionStart Warning on Exception as success (`Warning: load_session exception` / `Warning: bundle load failed` still injects additionalContext as work context) | C | typed CONTEXT_INCOMPLETE halt for required | s03, s05 | yes | `harness/hooks/epic/core.py` session_start_payload |
| MCP ok override partial required (`if not res.files and any missing_file` only) | C | same derive as core | s02, s05 | yes | Appetite cut = MCP **load rewrite**; override-on-partial **in-epic** |
| docs «pack wired» / CLAUDE pack table fully wired while doctor red | I | doctor green / honest red | s04, s05 | no | |
| «partial load ok» comments | I | required complete | s04, s05 | no | |
| n/a ffmpeg required as fail for software | — | advisory `pack_tool_gate_missing` if `tool_gates.required=true` | s01 documents | — | follow_up: T-HUB-051; Appetite cut |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-check-pack-graph-doctor.yaml](../yaml/steps/s01-check-pack-graph-doctor.yaml) | [s01…](../../implement/T-HUB-067-pack-doctor-executable-graph/s01-check-pack-graph-doctor.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-load-session-derived-ok.yaml](../yaml/steps/s02-load-session-derived-ok.yaml) | [s02…](../../implement/T-HUB-067-pack-doctor-executable-graph/s02-load-session-derived-ok.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-session-start-context-incomplete.yaml](../yaml/steps/s03-session-start-context-incomplete.yaml) | [s03…](../../implement/T-HUB-067-pack-doctor-executable-graph/s03-session-start-context-incomplete.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-kind-i-software-regression.yaml](../yaml/steps/s04-kind-i-software-regression.yaml) | [s04…](../../implement/T-HUB-067-pack-doctor-executable-graph/s04-kind-i-software-regression.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-legacy-fallback-purge.yaml](../yaml/steps/s05-legacy-fallback-purge.yaml) | [s05…](../../implement/T-HUB-067-pack-doctor-executable-graph/s05-legacy-fallback-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** все `no` (plan: CREATIVE need нет).

**Justification (5 sNN, не 7):** plan §До DECOMPOSE #1 red tests for route/gate/agent = same Path.exists outcome as #2 graph + #3 compose 062 — слиты в s01 (behavior-first §3a core+CLI / schema+paths). Load red (#1d/e) принадлежит s02 (другой noun: session ok). Purge остаётся отдельным s05 (apply ≠ purge). Kind I + software/video report — один instruction+regression pass (s04).
