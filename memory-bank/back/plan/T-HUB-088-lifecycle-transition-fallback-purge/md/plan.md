# [T-HUB-088 | lifecycle-transition-fallback-purge] PLAN

**Дата:** 2026-09-08  
**Режим:** BACK PLAN REFACTOR  
**Уровень:** L4  
**Статус:** draft  
**Clarify:** Phase 0 skipped — lifecycle replacement and old symbols are already named by T-HUB-029/T-HUB-070/T-HUB-074/T-HUB-077.  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `legacy-fallback-purge-20260908`  
**Deps:** hard T-HUB-087, T-HUB-029, T-HUB-070, T-HUB-074 and T-HUB-077.  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · python-design-patterns · python-anti-patterns

## Контекст и цель

Поздний `loop.epic_transition` уже является владельцем phase transition, projection и typed evidence, но старые `arm_active_context_from_decompose` и `arm_pre_implement_context` всё ещё содержат полноценные implementation bodies и вызываются из production. Дополнительно lifecycle сохраняет Markdown/raw handoff parsing, manual BUGFIX authority и artifact-only `mb-finish` compatibility.

Цель — перенести все call sites на canonical transition/evidence APIs, enforce fail-closed старого пути и удалить старые функции, ручные ветки и тесты, которые ожидают прежний lifecycle.

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Единственный transition/evidence lifecycle | `vertical_slice` | `loop.epic_transition.arm_phase` + `mb-finish`/Stop callers | legacy API/authority → explicit rejection | phase arm, QA→BUGFIX and finish scenarios | `n/a` |

## Product probe

| Реальная проблема | Wedge | Pre-mortem | Appetite |
|---|---|---|---|
| Одно состояние может быть armed старым API или новым transition engine | migrate direct callers, then delete old bodies and tests | скрытый import старого API оставит второй lifecycle owner | 4–5 дней; boundary first, cleanup last |

## WHAT

### User stories

| ID | Story | Priority | Independent test |
|---|---|---:|---|
| US-001 | Как loop, я хочу один phase transition owner, чтобы arm и auto-advance не расходились. | P0 | `arm_phase` проходит все lifecycle phases; legacy function import/call denied. |
| US-002 | Как gate, я хочу typed handoff/evidence без Markdown salvage и manual PASS fallback. | P0 | malformed/legacy handoff and manual receipt are rejected. |
| US-003 | Как QA/BUGFIX, я хочу сохранять текущий valid QA→BUGFIX→DONE outcome без artifact-only обхода. | P0 | valid receipt completes; missing/legacy evidence blocks. |

### Functional requirements

- **FR-001:** Все production callers старых arm-функций переходят на `loop.epic_transition.arm_phase`/canonical `arm_epic` API.
- **FR-002:** `arm_active_context_from_decompose`, `arm_pre_implement_context` и `_legacy_warn` удаляются после zero-caller proof.
- **FR-003:** `epic_resolve.py --decompose` и `context_loop.arm_session()` не вызывают legacy implementation body.
- **FR-004:** Handoff runtime принимает только typed `loop-handoff/v1`; malformed/transitional raw dict не продолжает lifecycle.
- **FR-005:** Manual BUGFIX authority и artifact-only mb-finish compatibility удаляются; verifier receipt становится обязательным.
- **FR-006:** Legacy REFLECT остаётся исторически игнорируемым event, но не участвует в live lifecycle decisions.
- **FR-007:** Старые transition/handoff/BUGFIX tests удаляются или переписываются на canonical behavior and deny coverage.

### Success criteria

| ID | Результат | Проверка | Type |
|---|---|---|---|
| SC-001 | 0 production callers legacy arm symbols | import/call-site rg | outcome |
| SC-002 | invalid/manual evidence cannot finish BUGFIX | targeted gate/finish tests | outcome |
| SC-003 | valid phase transition behavior unchanged | transition regression suite | outcome |
| SC-004 | no raw Markdown handoff fallback in runtime | schema/consumer inventory | outcome |

## Acceptance criteria

1. `arm_phase`/`arm_epic` — единственный live transition owner.
2. Старый `--decompose` input либо нормализуется в canonical epic id, либо завершается diagnostic; он не вызывает старую arm implementation.
3. `LoopHandoffFrontmatter` validation failure блокирует lifecycle, а не возвращает raw dict.
4. Manual BUGFIX receipt и artifact-only finish не проходят boundary.
5. Valid QA→BUGFIX→verify→finish flow остаётся зелёным.
6. Legacy REFLECT records do not change phase and do not reopen compatibility path.

### AC−

1. Нет production import/call для `arm_active_context_from_decompose`/`arm_pre_implement_context`.
2. Нет `authority == manual` как успешного verifier evidence.
3. Нет raw dict fallback из typed handoff parser.
4. Нет artifact-only finish path for active BUGFIX.
5. Нет тестов, которые закрепляют старый arm/handoff/BUGFIX contract.

## Technology axiom

| Выбор | Machine input | Запрещено после эпика |
|---|---|---|
| Phase transition | `arm_phase` typed transition request/result | direct core arm implementations |
| Handoff | validated `loop-handoff/v1` frontmatter | Markdown/raw dict salvage |
| Gate evidence | typed verifier receipt + identity | manual/non-authoritative PASS |
| Finish | explicit phase + receipt | artifact presence as phase proof |

## Refactor inventory

| ID | Path / symbol | Evidence and callers | Action | Replacement owner | Tests |
|---|---|---|---|---|---|
| L88-01 | `harness/hooks/epic/core.py:arm_active_context_from_decompose` | called from `epic_resolve.py`, `context_loop.py`, transition/core imports | migrate callers, delete body/export | `loop.epic_transition.arm_phase` | `test_epic_transition.py`, `test_epic_paths.py` |
| L88-02 | `harness/hooks/epic/core.py:arm_pre_implement_context` | transition engine delegates to it for PLAN/DECOMPOSE/ANALYZE | move canonical logic into transition owner, delete old symbol | `arm_phase` | `test_arm_phase_smoke.py`, transition tests |
| L88-03 | `loop/epic_transition.py:_legacy_warn` | used only by two old arm implementations | delete with old symbols | none | deprecation assertions |
| L88-04 | `harness/hooks/epic_resolve.py --decompose` fallback | unresolved target calls old arm function | normalize/deny without legacy body | `--epic-id` + resolver | CLI tests |
| L88-05 | `loop/context_loop.py:arm_session` legacy decompose branch | accepts v1 target and `require_plan=False` | canonicalize then enforce plan | `arm_epic` | context loop tests |
| L88-06 | `loop/schemas/active_context.py:parse_handoff_meta` raw dict fallback | validation failure returns untyped raw mapping | return structured error/None and block caller | `validate_handoff_frontmatter` | `test_schemas_handoff.py`, handoff gates |
| L88-07 | `_handoff_mode_from_legacy_markdown`, Markdown mode extraction | alias has no callers; mode parser still supports old text | delete dead alias; remove runtime Markdown fallback after writer audit | typed handoff | handoff phase tests |
| L88-08 | `harness/hooks/_lib.py:match_gate_evidence` manual fallback | manual authority returns success marker | reject manual evidence | verifier receipt validator | receipt integrity tests |
| L88-09 | `harness/hooks/epic/core.py:_verify_pass_ready_for_step` manual BUGFIX branch | explicit “until purged in s05” compatibility remains | delete branch | typed receipt | `test_finish_bugfix.py`, finish integrity |
| L88-10 | `loop/mb_finish/impl.py` artifact-only compatibility | legacy entry point can avoid persisted BUGFIX phase | require active phase + receipt | transaction boundary | mb-finish tests |
| L88-11 | session compatibility params/aliases | `track`, `expected_model`, old abort alias are retained for imports | delete only no-caller aliases; preserve needed runtime API until proof | canonical session identity | session resilience tests |
| L88-12 | REFLECT live references | current lifecycle ignores old handoff/event intentionally | keep historical ignore, remove live compatibility branches | QA→DONE lifecycle | `test_reducer_qa_bugfix.py` |

## Deletion budget

| Scope | Expected deletion | Rewire delta | Net concept target |
|---|---:|---:|---:|
| legacy arm bodies/warnings | 250–450 LOC | 6 direct callers | −3 transition owners |
| raw handoff/manual evidence | 40–100 LOC | typed validator calls | −2 evidence modes |
| artifact-only BUGFIX branch | 20–60 LOC | finish transaction guard | −1 finish bypass |
| obsolete lifecycle tests | 15–30 tests/assertions | 8–12 canonical deny/behavior tests | −1 legacy test family |

## Test refactor

- Add characterization tests for every phase currently routed through `arm_phase` before deleting core bodies.
- Rewrite tests that assert `DeprecationWarning` or direct calls to old arm functions into canonical transition tests.
- Replace raw Markdown handoff fixtures with typed valid, malformed and missing-frontmatter fixtures.
- Delete manual BUGFIX acceptance tests; retain negative tests proving manual evidence is rejected.
- Delete artifact-only finish tests; retain transaction tests requiring persisted phase and verifier receipt.
- Keep the historical `reflection_done` ignore test because it protects archive compatibility, not live fallback.

## HOW / data flow

```text
arm/finish entrypoint
  -> canonical transition request
  -> typed lifecycle state + handoff
  -> verifier receipt/identity check
  -> phase-specific finish or fail-closed diagnostic
```

## Failure matrix

| Link | Failure | Detection | Response | Test |
|---|---|---|---|---|
| arm request | legacy direct API | import/call scan | no symbol / explicit error | TM-088-01 |
| transition | malformed phase request | typed validator | fail-closed | TM-088-02 |
| handoff | invalid frontmatter | `validate_handoff_frontmatter` | block lifecycle | TM-088-03 |
| evidence | manual authority | receipt validator | reject | TM-088-04 |
| BUGFIX finish | missing persisted phase | transaction guard | block | TM-088-05 |
| archive event | old REFLECT event | dead-event classifier | ignore without phase change | TM-088-06 |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
|---|---|---|
| `arm_active_context_from_decompose` | `arm_phase`/`arm_epic` | delete in-epic |
| `arm_pre_implement_context` | canonical transition owner | delete in-epic |
| `_legacy_warn` | no public legacy callers | delete in-epic |
| manual evidence branch | typed verifier receipt | delete in-epic |
| artifact-only BUGFIX finish | transaction boundary | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|---|---|---|
| unresolved `--decompose` fallback execution | canonical `--epic-id` resolution or explicit failure | delete in-epic |
| legacy mb-finish phase omission | typed finish transaction | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|---|---|---|
| typed handoff failure → raw dict | validation error / halt | delete in-epic |
| manual evidence → accepted non-authoritative PASS | reject | delete in-epic |
| missing phase → artifact-only finish | phase+receipt requirement | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
|---|---|---|
| instructions calling old arm functions | `arm_phase`/`arm_epic` | delete/rewrite in-epic |
| instructions accepting manual BUGFIX evidence | typed verifier receipt | delete/rewrite in-epic |
| REFLECT as live next phase | QA→DONE / QA→BUGFIX rules | delete/rewrite in-epic |

## До DECOMPOSE (черновик нарезки)

1. Characterize all arm/finish phase behavior and direct callers.
2. Rewire transition and CLI callers to one owner.
3. Enforce typed handoff and receipt-only BUGFIX finish.
4. Remove manual/artifact-only compatibility branches.
5. Delete obsolete lifecycle tests and update instructions.
6. Execute final legacy-fallback purge and full regression.

## QA consumes

| ID | Priority | Scenario | Command / fixture | Expected | Maps |
|---|---:|---|---|---|---|
| TM-088-01 | P0 | old arm symbols have zero callers | `rg` import/call control | zero production hits | FR-001/002 |
| TM-088-02 | P0 | canonical phase arm parity | `bin/pytest loop/tests/test_epic_transition.py loop/tests/test_arm_phase_smoke.py -q` | PASS | FR-001 |
| TM-088-03 | P0 | malformed handoff denied | `bin/pytest loop/tests/test_schemas_handoff.py loop/tests/test_handoff_strict_flag.py -q` | no raw dict continuation | FR-004 |
| TM-088-04 | P0 | manual evidence denied | `bin/pytest loop/tests/test_finish_receipt_integrity.py loop/tests/test_finish_capability_evidence.py -q` | fail-closed | FR-005 |
| TM-088-05 | P0 | BUGFIX transaction requires phase/receipt | `bin/pytest loop/tests/test_finish_bugfix.py loop/tests/test_mb_finish_transaction.py -q` | valid path only | FR-005 |
| TM-088-06 | P1 | REFLECT archive event ignored | `bin/pytest loop/tests/test_event_legacy_adapter.py loop/tests/test_reducer_qa_bugfix.py -q` | no live phase change | FR-006 |
| TM-088-07 | P0 | sunset symbols/instructions scan | plan `rg` controls | zero old contract hits | AC− |
| TM-088-08 | P1 | full hub regression | `bin/pytest -q --tb=line` | PASS | SC-003 |

## Review readiness

| Gate | Required | Status | Evidence |
|---|---|---|---|
| Product probe | L3+ | done | §Product probe |
| Structural inventory | required | done | callers and symbol map |
| Refactor inventory | required | done | §Refactor inventory |
| Deletion budget | required | done | §Deletion budget |
| Test refactor | required | done | §Test refactor |
| Replacement/sunset A+B+C+I | required | done | §Replacement / sunset |
| QA consumes | required | done | TM-088-01…08 |
| Open CRITICAL | required | none | no unresolved blocker |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Decision |
|---|---|---|---|
| Product | behavior freeze: valid lifecycle remains unchanged | external imports of old symbols | prove before deletion; no silent shim |
| Engineering | transition owner absorbs old bodies before purge | no new transition abstraction | reuse existing `arm_phase` |

## Appetite

| Поле | Значение |
|---|---|
| `timebox_days` | 5 |
| `cut_list` | operational session resilience, historical archive rewriting, new lifecycle features |

## Следующий режим

→ **BACK DECOMPOSE T-HUB-088-lifecycle-transition-fallback-purge** after T-HUB-087 and queue reconcile.
