# [T-HUB-056 | suite-green-loop-identity] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** done  
**Clarify:** Phase 0 skipped — taxonomy clear (axioms из T-HUB-029 folder-stem, T-HUB-022 handoff, T-HUB-041 path move, T-HUB-044 doctor)  
**Roadmap:** [roadmap-suite-hygiene-epics.md](roadmap-suite-hygiene-epics.md)  
**Deps hard:** T-HUB-055 (после board-sync; цепочка 054→055→056→053)  
**Baseline nodeids (fresh, 11):**

| Nodeid | Кластер |
|--------|---------|
| `test_context_loop.py::test_prepare_builds_prompt_with_activecontext` | prepare/fixtures |
| `test_context_loop.py::test_check_after_commits_next_step_for_post_implement_phase` | check_after |
| `test_context_loop.py::test_check_after_continues_when_handoff_advanced` | check_after |
| `test_context_loop.py::test_prepare_promotes_analyze_to_implement_when_gate_passes` | promote + epic_resolve path |
| `test_drift_display.py::test_status_shows_drift_when_nonzero` | handoff shape / drift |
| `test_epic_transition.py::test_arm_pre_implement_short_queue_id_uses_plan_stem` | epic_id stem |
| `test_episode_wire.py::test_check_after_creates_manifest` | episode |
| `test_episode_wire.py::test_finalize_exception_does_not_block` | episode |
| `test_incidents_doctor.py::test_doctor_valid_project_exit_zero` | doctor |
| `test_incidents_doctor.py::test_doctor_open_incidents_warn_only` | doctor |
| `test_incidents_doctor.py::test_doctor_boundary_check_warn` | doctor |
| `test_incidents_doctor.py::test_doctor_boundary_check_pass` | doctor |

(4 doctor + 4 context_loop + 2 episode + drift + stem = 12 строк таблицы; baseline rg показал 4 doctor + … = часть из 19.)

→ decompose после DECOMPOSE

## Контекст

- req: loop identity и doctor снова согласованы с post-041 paths и plan-stem epic_id; full suite → 0 failed после 054+055+056
- deps: T-HUB-054; soft T-HUB-029, T-HUB-022, T-HUB-041, T-HUB-044, T-HUB-031 (episode)
- refs: `test_arm_pre_implement_short_queue_id_uses_plan_stem` (ожидает `T-HUB-023-hooks-llm-fallbacks`); promote error: missing `.claude/hooks/epic_resolve.py` в tmp fixture; drift: `missing_handoff_frontmatter`

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Epic folder identity | **plan stem** `T-HUB-023-hooks-llm-fallbacks` (decompose/plan paths) | short queue id как `armed_epic` / handoff `epic_id` когда plan stem существует |
| Hook entrypoint в fixtures | path через hub resolve (`harness/hooks` / symlink `.claude/hooks`) | hardcode только pre-041 layout без provision |
| Status/drift | handoff frontmatter `loop-handoff/v1` | status без handoff, но assert drift_counters |
| Doctor | current doctor CLI contract (T-HUB-044) | ослабить exit codes «чтобы green» |

## Продуктовая спека (WHAT)

Loop и doctor должны:

1. Резолвить epic identity в **полный stem**, совпадающий с `plan-*.md` / `decompose-*` папками.  
2. Готовить/проверять сессии на фикстурах, где entrypoints hooks существуют (или резолвятся) после harness extract.  
3. Показывать drift только при валидном handoff shape.  
4. Давать doctor предсказуемые exit codes на валидном/warn проекте.

Итог для оператора: `bin/pytest` = 0 failed.

## Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Identity/path drift после 029/041/044 ломает suite и доверие QA | fix prod stem + fixtures |
| 2 | Wedge | Сначала stem + promote path; потом drift fixtures; doctor; episode | ordered sNN |
| 3 | Pre-mortem | Перепишем тест stem на short id | FORBIDDEN — AC test = SoT folder naming |
| 4 | Adoption | full suite gate | SC 0 failed |
| 5 | Leverage | Не трогать board | 055 |
| 6 | Appetite | 3 дня | cut: session_wrapper hang deep-dive если снова red |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как loop, я хочу arm по short queue id писал stem в state/activeContext, чтобы decompose path совпал с диском. | P0 | `test_arm_pre_implement_short_queue_id_uses_plan_stem` PASS (`epic_id` / `armed_epic` = stem). |
| US-002 | Как prepare, я хочу validate-traceability находить epic_resolve в тестовом cwd, чтобы promote analyze→implement не halt на ENOENT. | P0 | `test_prepare_promotes_analyze_to_implement_when_gate_passes` PASS. |
| US-003 | Как оператор status, я хочу drift_counters при валидном handoff. | P0 | `test_status_shows_drift_when_nonzero` PASS. |
| US-004 | Как doctor user, я хочу doctor exit 0/warn по контракту на fixture project. | P0 | все 4 `test_incidents_doctor.py::*` из baseline PASS. |
| US-005 | Как QA, я хочу full suite green. | P0 | `bin/pytest -q --tb=no` → 0 failed (после 054+055+056). |

#### Acceptance Scenarios — US-001

- **Given:** plan file `plan-T-HUB-023-hooks-llm-fallbacks.md`, arm `epic_id="T-HUB-023"`
- **When:** `arm_pre_implement_context(...)`
- **Then:** returned/state/activeContext epic_id = `T-HUB-023-hooks-llm-fallbacks`

#### Acceptance Scenarios — US-002

- **Given:** tmp project с handoff ANALYZE gate pass
- **When:** prepare promote
- **Then:** ok True; нет ENOENT `epic_resolve.py` (fixture копирует/линкует harness hooks)

### Functional Requirements

- **FR-001:** `arm_pre_implement_context` / `loop.epic_transition` резолвит short id → plan stem, если plan файл со stem существует (AC теста = канон).
- **FR-002:** context_loop / promote fixtures provision `epic_resolve` (или patch path) post-T-HUB-041 layout.
- **FR-003:** drift_display / status tests используют валидный `loop-handoff/v1` frontmatter (rewrite fixtures, не disable shape gate).
- **FR-004:** doctor tests выровнены под T-HUB-044 doctor behavior (exit codes/JSON); prod чинится только если расходится с implement doctor.
- **FR-005:** episode_wire check_after/finalize согласованы с текущим episode API (T-HUB-031); rewrite или fix prod per implement.
- **FR-006:** context_loop check_after/prepare remaining FAIL — тот же method lock (implement → action).
- **FR-007:** После закрытия cluster: **full suite 0 failed** (SC финальный roadmap).

### Success Criteria

| ID | Результат | Проверка | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | stem test PASS | targeted | outcome |
| SC-002 | context_loop 4 PASS | targeted | outcome |
| SC-003 | doctor 4 PASS | targeted | outcome |
| SC-004 | episode 2 PASS | targeted | outcome |
| SC-005 | drift PASS | targeted | outcome |
| SC-006 | `bin/pytest` 0 failed | full suite | outcome |

### Assumptions

- Short id без plan file может оставаться short (out of scope) — тест даёт plan file.
- Session_wrapper hang из старого inventory — если снова появится в fail-list после 054 timeout, добавить sNN; иначе out.

### Clarifications

- Cluster G naming: `t035_*` в старом inventory ≠ epic T-HUB-035 boundaries; если снова red — отдельная строка в DECOMPOSE, не путать с architecture-boundaries.

## AC

1. Все baseline nodeids этого эпика PASS.  
2. Full suite 0 failed (совместно с 054+055).  
3. Каждое изменение трассируется к implement yaml.  
4. Purge: нет тестов, требующих short-id-only identity при наличии plan stem.

### AC−

1. Нет «ослабить stem тест до short id».  
2. Нет disable shape/handoff gate ради drift assert.  
3. Нет silent doctor exit 0 при реальном fail.  
4. Нет dual epic_id (short в state + stem в path) без явного ADR.  
5. Нет executable tests на удалённый `.claude/hooks` layout без provision.

## Техника / HOW

- Модули: `harness/hooks/epic/core.py` (arm), `loop/epic_transition.py`, `loop/context_loop.py`, `loop/tests/test_*`, doctor CLI (`loop` incidents/doctor), episode wire
- Типичные фиксы: resolve_stem helper; conftest copy hooks tree; handoff YAML frontmatter в fixtures; doctor expect sync with T-HUB-044

## Eng review spine

### Data flow

```text
[arm short id] -> [resolve plan stem] -> [epic state + activeContext]  sync fail-closed if ambiguous multi-plan
[prepare] -> [validate-traceability via epic_resolve path] -> [promote / halt]
[status] -> [shape gate handoff] -> [drift_counters]
[doctor] -> [checks registry/boundaries/incidents] -> [exit code]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| arm returns short | stem assert | pytest | fix resolve | TM-001 |
| ENOENT epic_resolve | promote halt | pytest log | fixture provision | TM-002 |
| missing handoff FM | no drift_counters | status JSON | fix fixture | TM-003 |
| doctor exit drift | assert exit | pytest | align contract | TM-004 |
| episode API drift | assert | pytest | rewrite/fix | TM-005 |
| suite still red | fail-list | full pytest | leftover sNN | TM-006 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow | 5 | — |
| Failure coverage | 4 | session hang optional |
| Testability | 5 | — |

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| arm writing short id when plan stem exists | stem identity | delete in-epic (behavior) |
| Fixtures assuming only pre-041 `.claude/hooks` without files | provision harness/claude hooks | delete in-epic |
| Tests asserting doctor old exit without T-HUB-044 AC | rewrite to 044 contract | delete in-epic / rewrite |
| Dual identity short+stem | single stem in handoff/state | delete in-epic |

### B. Entrypoints

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | doctor/prepare same CLI | n/a |

### C. Fallbacks

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| on missing epic_resolve → skip validate | fail-closed / fixture must provide | delete in-epic |
| on missing handoff → invent drift | shape error, no fake counters | keep shape gate |

## QA consumes

### Scope

- context_loop, epic_transition stem, drift_display, incidents_doctor, episode_wire; final full suite

### Test matrix

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | plan stem | `bin/pytest loop/tests/test_epic_transition.py::test_arm_pre_implement_short_queue_id_uses_plan_stem -q` | PASS | FR-001 |
| TM-002 | P0 | promote | `bin/pytest loop/tests/test_context_loop.py::test_prepare_promotes_analyze_to_implement_when_gate_passes -q` | PASS | FR-002 |
| TM-003 | P0 | context_loop cluster | `bin/pytest loop/tests/test_context_loop.py -k 'prepare_builds or check_after_commits or check_after_continues or promotes_analyze' -q` | PASS | FR-006 |
| TM-004 | P0 | drift | `bin/pytest loop/tests/test_drift_display.py::test_status_shows_drift_when_nonzero -q` | PASS | FR-003 |
| TM-005 | P0 | doctor | `bin/pytest loop/tests/test_incidents_doctor.py -q` | PASS | FR-004 |
| TM-006 | P0 | episode | `bin/pytest loop/tests/test_episode_wire.py -q` | PASS | FR-005 |
| TM-007 | P0 | full suite | `bin/pytest -q --tb=no` | 0 failed | FR-007 SC-006 |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | §Product probe |
| Eng review spine | L2+ | done | filled |
| §0.11 | draft | done | arm↔plan path↔activeContext; doctor↔registry |
| CREATIVE | n/a | n/a | — |
| qa_consumes | L2+ | done | ≥7 TM |
| Plan review batch | L2+ | done | below |

## Plan review batch log

| Phase | Auto-resolved | Deferred | CRITICAL |
|-------|---------------|----------|----------|
| Product | stem test = SoT (not weaken) | session_wrapper if reappears | none open |
| Eng | ENOENT = fixture/path post-041 | — | none |

## До DECOMPOSE

1. **s01** — arm/epic_transition short→stem resolve (TDD stem test)  
2. **s02** — context_loop fixtures + promote path provision  
3. **s03** — remaining context_loop check_after/prepare  
4. **s04** — drift_display handoff fixtures  
5. **s05** — incidents_doctor align T-HUB-044  
6. **s06** — episode_wire  
7. **s07** — full suite green gate + leftover mop  
8. **s08-legacy-fallback-purge** — sunset inventory identity/path; no short-id dual; no missing-resolve skip

## Appetite

| Поле | Значение |
| :--- | :--- |
| `timebox_days` | `3` |
| `cut_list` | `['session_wrapper deep hang if not in fail-list', 'extra doctor docs']` |

## Следующий режим

→ BACK DECOMPOSE после T-HUB-054 (и рекомендуется после/рядом с 055)
