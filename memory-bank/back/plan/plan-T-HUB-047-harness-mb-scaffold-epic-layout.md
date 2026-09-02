# [T-HUB-047 | harness-mb-scaffold-epic-layout] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-036 (`formula-render` → merge в `mb-scaffold decompose`), T-HUB-040 (`mb-finish` path refs + FINISH). **Soft:** T-HUB-045 (`mb-load` bundle paths), T-HUB-024 (`validate-traceability` → `plan.yaml` first), T-HUB-029 (session arm / transition), T-HUB-034 (janitor globs).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [decompose-T-HUB-047-harness-mb-scaffold-epic-layout/index.md](decompose-T-HUB-047-harness-mb-scaffold-epic-layout/index.md) — **после DECOMPOSE** (новый layout: `plan/<epic_id>/…`)

---

## Контекст

- **req:** Снизить output-токены агента на workflow-фазах с YAML-артефактами: runtime (CLI) создаёт **скелетоны** (schema-valid, пустые семантические поля), агент только **fill/edit**. Добавить machine sidecar `epic-plan/v1` (`plan.yaml`) с `requirements[]` + `outline_steps[]` (floor) для детерминированной нарезки decompose. Упорядочить FS: **один каталог на эпик**, внутри `md/` и `yaml/`, без свалки `plan-*.md` + `decompose-*` в корне `plan/`.
- **gap (as-built):**
  - DECOMPOSE: агент **Write** полные `sNN-*.yaml` + `index.md` coverage с нуля → тысячи output-токенов на эпик.
  - `formula-render` (T-HUB-036): structural draft, **не** skeleton mode; не создаёт `index.md`; не привязан к `plan.yaml`; не вызывается loop/session-start.
  - `seed-implement`: по одному shard; нет `--all`; пути legacy `implement/implement-<id>/`.
  - Пути размазаны: `epic_paths.py`, `reconcile.py`, `context_loop.py`, `_lib.py` regex — хардкод `plan/decompose-{id}/`, `plan/plan-{id}.md`.
  - `validate-traceability`: regex по `plan.md`; нет machine `requirements[]`.
  - Workflow rules описывают старый flat layout; loop/arm/finish/load сломаются при смене путей без единого resolver.
- **refs:** чат 2026-09-02 (mb-scaffold + epic layout v2 + path migration HARD); T-HUB-040/045 symmetric API pattern; `loop/YAML-CONTRACT.md`; `.cursor/rules/shared/epic-scoped-paths.mdc`.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Epic FS layout | `epic-layout/v2` resolver (`loop/paths/epic_layout.py`) | ad-hoc glob `decompose-*` в loop/hooks |
| Plan machine spec | `epic-plan/v1` pydantic → `plan/<epic_id>/yaml/plan.yaml` | regex-only requirement extract как primary |
| Scaffold request | `mb-scaffold-request/v1` JSON CLI | агент Write нового yaml tree с нуля |
| Scaffold output | empty semantic fields + schema + plan-derived rows | generic formula goals как «готовый» decompose |
| Path resolve | `resolve_epic_path(kind, epic_id)` единственный API | дублирующие path helpers |
| Legacy layout | migrate script + resolver alias **один** эпик | вечный dual-path без purge step |

DECOMPOSE → purge-step: удалить прямые строки `plan/plan-*.md`, `plan/decompose-*` из loop/hooks после migrate; workflow → resolver + mb-scaffold.

---

## Продуктовая спека (WHAT)

### Product probe (Phase 0 skipped — taxonomy clear)

| # | Question | Answer / Probe | Decision / Impact |
|---|----------|----------------|-------------------|
| 1 | **Reframe:** Какую проблему решаем? | LLM тратит output на boilerplate yaml/md; path drift ломает loop при любом rename | Фокус = scaffold CREATE + layout v2 + resolver, не «ещё один render» |
| 2 | **Narrowest wedge:** Минимальный slice? | resolver + migrate + `mb-scaffold plan|decompose` + loop smoke | IMPLEMENT scaffold (`--all`) — phase 2 в том же эпике |
| 3 | **Pre-mortem:** Провал через месяц? | Сменили пути, забыли loop → всё red | Path migration = blocking AC; pytest matrix до merge |
| 4 | **Distribution:** Кто вызывает? | session-start / arm_phase / parent agent via CLI | Не implicit в LLM prose |
| 5 | **Technical leverage:** Что переиспользовать? | `formula_render`, `seed_implement`, `mb_finish` schemas, `extract_load_now` | Один пакет `loop/mb_scaffold/` |
| 6 | **Appetite:** Стоит ли? | Да — −50–70% output tokens на DECOMPOSE+PLAN FINISH; разблокирует mb-load точные paths | L3–L4, ~10–12 sNN |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как planner, я хочу `plan.yaml` с `outline_steps` и `summary.step_count_floor`, чтобы CLI знал минимум задач до DECOMPOSE. | P0 | `mb-scaffold plan` → yaml с N outline_steps; `validate-plan-spec` exit 0 |
| US-002 | Как operator DECOMPOSE, я хочу `mb-scaffold decompose --from-plan` создал tree до агента, чтобы агент только edit fill. | P0 | scaffold → empty delta; agent forbidden Write new sNN file; `validate-decompose-tree` green |
| US-003 | Как platform, я хочу единый path resolver, чтобы loop/arm/finish/load не ломались при layout v2. | P0 | pytest resolver matrix; `arm_phase` smoke на новом layout |
| US-004 | Как operator, я хочу migrate script flat→v2 для существующих эпиков. | P0 | migrate dry-run + apply; `validate-decompose-tree` на migrated tree |
| US-005 | Как parent IMPLEMENT, я хочу `mb-scaffold implement --all` из decompose index. | P1 | N implement yaml in_progress, cp pending |
| US-006 | Как operator QA/ANALYZE, я хочу phase scaffold из epic context. | P1 | `mb-scaffold qa|analyze` → schema-valid empty findings |
| US-007 | Как auditor, я хочу `validate-traceability` читал `plan.yaml` requirements без regex md. | P1 | fixture missing FR → CRITICAL from yaml inventory |
| US-008 | Как DECOMPOSE agent, я хочу добавить sNN сверх outline floor при coverage gap. | P0 | scaffold 5 steps; agent adds s06; traceability still green |

#### Acceptance Scenarios — US-002

- **Given:** `plan/<epic_id>/yaml/plan.yaml` с 5 `outline_steps`, PLAN FINISH done
- **When:** `epic_resolve.py mb-scaffold decompose --epic-id <id> --cwd $PROJECT_ROOT`
- **Then:** `plan/<epic_id>/yaml/steps/s01..s05.yaml` exist, `delta: []`, `md/decompose-index.md` coverage rows with empty sNN column; JSON `ok:true`

#### Acceptance Scenarios — US-008

- **Given:** scaffolded decompose 5 steps; plan FR-006 uncovered
- **When:** agent adds `s06-*.yaml` + updates coverage tables
- **Then:** `validate-traceability` CRITICAL=0; `verify-decompose` semantic gate still required

### Functional Requirements (FR-###)

- **FR-001:** Schema `loop/schemas/plan_spec.py` — `epic-plan/v1`: `plan_id`, `level`, `formula?`, `summary{step_count_floor, requirement_count}`, `requirements[]`, `outline_steps[]`, `stages[]`, `sunset_refs[]`, `technology_axiom`.
- **FR-002:** Schema `loop/schemas/epic_layout.py` — `epic-layout/v2` path kinds: `plan_md`, `plan_yaml`, `decompose_index_md`, `decompose_index_yaml`, `decompose_step`, `implement_step`, `qa_yaml`, `analyze_yaml`, `audit_yaml`.
- **FR-003:** Module `loop/paths/epic_layout.py` — `resolve(role, epic_id, kind, step_id?) -> Path`; **единственный** path API для loop + harness (re-export in `harness/hooks/epic_paths.py` thin wrapper).
- **FR-004:** Module `loop/mb_scaffold/` — `scaffold_plan`, `scaffold_decompose`, `scaffold_implement_all`, `scaffold_qa`, `scaffold_analyze`, `scaffold_audit`; pydantic request/result models (`mb-scaffold-result/v1`).
- **FR-005:** CLI `epic_resolve.py mb-scaffold <subcmd>`: `plan`, `decompose`, `implement`, `qa`, `analyze`, `audit`; flags `--epic-id`, `--force`, `--dry-run`, decompose: `--from-plan`, `--formula`.
- **FR-006:** Skeleton contract: semantic fields empty (`delta: []`, `as_built: []`, `goal: ""` or placeholder comment block); schema + `step_id` + `plan_refs` pre-filled from `outline_steps.maps_to`; **не** generic formula goals.
- **FR-007:** `mb-scaffold plan` writes `md/plan.md` (section headers from template) + `yaml/plan.yaml` (minimal valid spec); operator/agent fills prose in md + enriches yaml on PLAN FINISH.
- **FR-008:** `mb-scaffold decompose` reads `plan.yaml` outline → steps + index; optional `--formula` merges formula step titles into outline **floor only**.
- **FR-009:** Migrate `loop/formula_render.py` output target → resolver paths under `plan/<epic_id>/decompose/yaml/steps/`; deprecate flat `decompose-<id>/` output (purge in s11).
- **FR-010:** Migrate script `loop/migrate/epic_layout_v1_to_v2.py` — `--dry-run|--apply`; moves `plan-<id>.md`, `decompose-<id>/` → `plan/<id>/…`; updates internal refs in yaml/md; idempotent.
- **FR-011:** **Loop integration (HARD):** `context_loop.py`, `arm_phase`, transition engine, `finalize_step`, parallel orchestrator, board sync, janitor globs — **only** via `epic_layout.resolve`; zero hardcoded `decompose-*` after purge step.
- **FR-012:** **Harness integration (HARD):** `epic/core.py`, `reconcile.py`, `seed_implement`, `mb_finish/*`, `session_resilience.py`, `_lib.py` regex — resolver; compat alias for legacy paths **until** migrate applied (diagnostic `layout_v1_deprecated`).
- **FR-013:** **Workflow rules (HARD):** update `epic-scoped-paths.mdc`, `workflow-{plan,decompose,implement,archive}.mdc` (BACK/FRONT/INTEG), `memory-bank-paths.mdc`, templates, `YAML-CONTRACT.md`, `plan-artifact.md` — document layout v2 + «FORBIDDEN Write scaffolded yaml from scratch; Edit only».
- **FR-014:** `validate-traceability` — primary inventory from `plan.yaml` `requirements[]`; md fallback **удалить** in purge step.
- **FR-015:** `mb-load` (T-HUB-045): bundle paths via resolver when epic ships.
- **FR-016:** session-start / `arm_phase`: optional auto `mb-scaffold <phase>` on phase enter when tree missing (fail-closed if plan invalid).
- **FR-017:** Tests: ≥25 pytest covering resolver, scaffold modes, migrate, loop arm smoke, mb-finish path, forbidden agent Write policy (doc test / grep gate).
- **FR-018:** Hub self-test cwd guard on all mb-scaffold subcommands.

### Success Criteria

| ID | Измеримый результат | Проверка | Type |
|----|---------------------|----------|------|
| SC-001 | Layout v2 resolver 100% loop hot paths | pytest `test_epic_layout_resolver_loop_smoke` | outcome |
| SC-002 | Migrate all active hub epics dry-run 0 errors | CLI migrate dry-run on dev-hub memory-bank | outcome |
| SC-003 | DECOMPOSE scaffold 5-step epic: agent edit-only | harness doc gate + manual smoke doc | outcome |
| SC-004 | No hardcoded `plan/decompose-` in loop/ after purge | `rg` gate pytest | outcome |
| SC-005 | validate-traceability reads plan.yaml | pytest FR coverage | outcome |

### Assumptions

- Epic id stem unchanged (`T-HUB-047-harness-…`); меняется только FS nesting.
- Active IMPLEMENT epics (T-HUB-033, T-HUB-040, …) мигрируются migrate script **до** purge legacy resolver (s10 apply, s11 purge).
- Prose `plan.md` остаётся canonical для WHAT; `plan.yaml` — machine boundary only.
- INTEG `eNN` layout mirrors `sNN` under `integration/plan/<epic_id>/`.

### Anti-scope

- LLM-side automatic scaffold without CLI (prose «создай файлы» остаётся запрещён).
- Сокращение plan.md / decompose maximal detail (§0.0 still applies to **content** after fill).
- Subagent parallel DECOMPOSE writers (отдельный эпик).
- Product `$PROJECT_ROOT` rollout вне dev-hub memory-bank.

### Clarifications

- Session: чат 2026-09-02 — согласовано: scaffold CLI + agent fill; outline floor + agent may add steps; path migration обязателен для loop/workflow.
- T-HUB-045 может ship параллельно; mb_load должен consume resolver when both present.

---

## AC

1. `epic-plan/v1` + `epic-layout/v2` pydantic schemas validated on write.
2. `loop/paths/epic_layout.py` resolver — единственный path source in loop+harness (post-purge).
3. `mb-scaffold` CLI: plan, decompose, implement (--all), qa, analyze, audit.
4. Skeleton contract documented; workflow FORBIDDEN full Write on scaffolded paths.
5. Migrate script v1→v2 + apply on dev-hub memory-bank.
6. Loop + harness integration green: `pytest loop/tests harness/hooks/tests`.
7. `validate-traceability` plan.yaml primary.
8. formula-render merged into mb-scaffold decompose (--formula).
9. Legacy path purge step (no dual glob in loop/).
10. Workflow + epic-scoped-paths + templates updated.

### AC− (brownfield replace)

1. Нет второго path resolver кроме `epic_layout.resolve`.
2. Нет агент Write нового `sNN.yaml` когда scaffold tree exists (workflow gate).
3. Misconfig epic_id → JSON `ok:false`, не partial scaffold в wrong dir.
4. Нет вечного v1+v2 dual path в loop после purge без queue follow-up.
5. Нет regex+plan.yaml hybrid на requirement inventory boundary (yaml primary post-purge).

---

## Техника / HOW

### Epic layout v2 (канон FS)

```text
memory-bank/{role}/plan/{epic_id}/
  md/
    plan.md                    # WHAT/HOW prose (plan-artifact bar)
    decompose-index.md         # coverage tables (prose)
  yaml/
    plan.yaml                  # epic-plan/v1
    decompose-index.yaml       # epic-decompose-index/v1
    steps/
      sNN-<slug>.yaml          # epic-decompose/v1

memory-bank/{role}/implement/{epic_id}/
  yaml/
    steps/
      sNN-<slug>.yaml          # epic-implement/v1

memory-bank/{role}/qa/{epic_id}/yaml/qa-YYYYMMDD-<slug>.yaml
memory-bank/{role}/analyze/{epic_id}/yaml/analyze-YYYYMMDD-<slug>.yaml
memory-bank/{role}/audit/{epic_id}/yaml/audit-YYYYMMDD-<slug>.yaml
```

**Legacy (v1 — sunset):**

```text
plan/plan-{epic_id}.md
plan/decompose-{epic_id}/index.{md,yaml}
implement/implement-{epic_id}/sNN.yaml
```

Resolver: try v2 first; v1 compat **только** до migrate+purge (diagnostic warning).

### Модули

| Path | Role |
|------|------|
| `loop/schemas/plan_spec.py` | `EpicPlanSpec` epic-plan/v1 |
| `loop/schemas/epic_layout.py` | layout kinds enum + validation |
| `loop/paths/epic_layout.py` | `resolve()`, `epic_root()`, `list_steps()` |
| `loop/mb_scaffold/plan.py` | scaffold_plan |
| `loop/mb_scaffold/decompose.py` | scaffold_decompose (+ formula merge) |
| `loop/mb_scaffold/implement.py` | scaffold_implement_all (wrap seed) |
| `loop/mb_scaffold/qa.py` | scaffold_qa |
| `loop/mb_scaffold/analyze.py` | scaffold_analyze |
| `loop/mb_scaffold/audit.py` | scaffold_audit |
| `loop/mb_scaffold/schemas.py` | request/result models |
| `loop/migrate/epic_layout_v1_to_v2.py` | migrate CLI |
| `harness/hooks/epic_paths.py` | thin re-export / delegate |
| `harness/hooks/epic_resolve.py` | `mb-scaffold` subparser |
| `loop/context_loop.py` | arm/finalize paths via resolver |
| `loop/formula_render.py` | output paths → v2 |

### epic-plan/v1 (outline floor)

```yaml
schema: epic-plan/v1
plan_id: T-HUB-047-harness-mb-scaffold-epic-layout
level: L3
formula: null
summary:
  step_count_floor: 11
  requirement_count: 18
requirements:
  - id: FR-001
    priority: P0
    text: "EpicPlanSpec pydantic schema"
outline_steps:
  - id: s01
    title: epic-layout resolver
    maps_to: [FR-002, FR-003]
stages: []
technology_axiom:
  machine_boundary: pydantic
  forbidden: ["regex requirement inventory", "dual path resolver"]
```

`outline_steps` = **floor**; DECOMPOSE may append steps; `summary.step_count_floor` = `len(outline_steps)` at PLAN FINISH.

### Data flow (ASCII)

```text
[PLAN FINISH]
    | mb-scaffold plan (optional bootstrap at PLAN start)
    v
[plan/<epic_id>/md/plan.md + yaml/plan.yaml]
    | operator/agent fills prose + outline_steps
    v
[DECOMPOSE session start / arm_phase]
    | mb-scaffold decompose --from-plan [--formula]
    v
[yaml/steps/s01..sN skeletons + md coverage empty rows]
    | agent Edit only (delta, skills, coverage, +sNN if needed)
    v
[validate-decompose-tree + validate-traceability + verify-decompose]
    |
    v
[IMPLEMENT session]
    | mb-scaffold implement --all
    v
[implement/<epic_id>/yaml/steps/* in_progress]
    | agent code + tests
    v
[mb-finish implement]  (paths via resolver)
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| mb-scaffold plan | invalid epic-plan/v1 | pydantic ValidationError | JSON ok:false exit 2 | TM-001 |
| mb-scaffold decompose | plan.yaml missing outline | precheck | ok:false `plan_spec_missing` | TM-002 |
| resolver | unknown kind | ValueError | ok:false | TM-003 |
| migrate v1→v2 | orphan refs | migrate validator | dry-run lists blockers | TM-004 |
| loop arm | legacy path only | arm smoke | compat alias + warning | TM-005 |
| scaffold + agent | Write new sNN bypass | workflow grep gate | FAIL doc review | TM-006 |
| traceability | FR not in yaml | validate-traceability | CRITICAL | TM-007 |
| wrong cwd | hub vs product | path guard | fail-closed | TM-008 |
| formula+plan merge | title collision | merge policy | deterministic slug suffix | TM-009 |
| purge premature | active v1 epic | migrate check | halt purge | TM-010 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 4 | TM-010 migrate guard in s10 |
| Testability | 5 | matrix per subcmd |

### §0.11 counterparts (draft)

| Ref in plan/code | Counterpart | Verify |
|------------------|-------------|--------|
| `epic_resolve.py mb-scaffold` | subparser dispatch | `mb-scaffold --help` |
| `loop/paths/epic_layout.resolve` | used in context_loop arm | rg import + smoke |
| `plan.yaml` requirements | decompose `plan_refs` | validate-traceability |
| `mb-finish` paths | resolver in finish_implement | pytest mb_finish |
| `mb-load` paths | resolver in load_session | pytest mb_load when 045 merged |
| workflow FORBIDDEN Write | decompose workflow.mdc | rg gate |
| migrate script | memory-bank trees | dry-run CLI |
| janitor globs | epic_layout.list_epics | janitor test update |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
|------------|--------|--------|
| Flat `plan/decompose-{id}/` glob in loop | `epic_layout.resolve` | delete in-epic s11 |
| `formula-render` standalone output dir flat | `mb-scaffold decompose --formula` | delete standalone path in s09 |
| Regex plan.md FR inventory primary | `plan.yaml` requirements | delete in-epic s08 |
| Scattered path helpers in reconcile | resolver delegate | delete duplicates s04 |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
|------------|--------|--------|
| Manual agent Write decompose tree | `mb-scaffold decompose` | workflow rule s07 |
| `seed-implement` one-by-one only | `mb-scaffold implement --all` | keep seed single as internal |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
|------------|--------|--------|
| «если нет yaml — напиши файл» | fail-closed scaffold missing | delete in-epic |
| v1 path silent resolve after purge | fail-closed `layout_unknown` | delete in-epic s11 |
| formula-render generic goals as done | skeleton empty delta | delete in-epic |

**Финальный purge sNN:** `s11-legacy-layout-purge` — rg gate: 0 `plan/decompose-` hardcode in `loop/`; 0 v1-only glob without resolver.

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic: T-HUB-047 — `loop/paths/`, `loop/mb_scaffold/`, migrate, resolver wiring loop+harness, workflow path docs.
- Out of scope: FRONT/INTEG product repos; MCP wrapper (P2).

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | scaffold plan writes v2 tree | pytest tmp_path | plan.md+yaml exist | FR-007, US-001 |
| TM-002 | P0 | scaffold decompose from plan outline | pytest 5 steps | 5 skeleton yaml | FR-008, US-002 |
| TM-003 | P0 | resolver v2 paths | pytest kinds matrix | correct paths | FR-003, US-003 |
| TM-004 | P0 | migrate dry-run hub sample | pytest fixture v1 | manifest ok | FR-010, US-004 |
| TM-005 | P0 | loop arm smoke v2 | pytest context_loop | arm ok | FR-011 |
| TM-006 | P1 | scaffold implement --all | pytest | N implement yaml | FR-005, US-005 |
| TM-007 | P1 | traceability plan.yaml | pytest missing FR | CRITICAL | FR-014, US-007 |
| TM-008 | P1 | agent add s06 over floor | pytest traceability | green | US-008 |
| TM-009 | P1 | mb-finish path resolver | pytest mb_finish | ok:true | FR-012 |
| TM-010 | P0 | purge rg gate loop | pytest rg gate | 0 legacy hardcode | AC-9 |

### Regression notes

- Run full `loop/tests` + `harness/hooks/tests` after s10 migrate apply.
- Order: resolver (s01–s03) before loop wire (s05); migrate (s10) before purge (s11).

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | done | §Product probe skip+reason |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external refs in HOW | done | §0.11 table |
| CREATIVE | if flagged | n/a | §CREATIVE need: нет |
| qa_consumes draft | L2+ | done | §QA consumes ≥3 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

**FINISH PLAN allowed:** no `pending` in Required rows for epic level.

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product (brainstorming) | outline=floor not ceiling; agent may add sNN | — | — |
| Eng (architecture-patterns) | single resolver; mb-scaffold symmetric to mb-finish/mb-load | mb-load wiring if 045 not merged: soft deps | path migration blocking |

---

## До DECOMPOSE (черновик нарезки — advisory floor)

| sNN | Slice |
|-----|-------|
| s01 | `epic-plan/v1` + `epic-layout/v2` pydantic schemas |
| s02 | `loop/paths/epic_layout.py` resolver + unit tests |
| s03 | `loop/mb_scaffold/schemas.py` + CLI dispatcher skeleton |
| s04 | harness `epic_paths` delegate + reconcile bundle paths |
| s05 | **loop integration** — context_loop arm/finalize/parallel/board |
| s06 | `mb-scaffold plan` + `mb-scaffold decompose` |
| s07 | workflow rules + templates + YAML-CONTRACT + epic-scoped-paths |
| s08 | `validate-traceability` plan.yaml primary |
| s09 | formula-render merge → mb-scaffold `--formula` |
| s10 | migrate script v1→v2 + apply dev-hub memory-bank |
| s11 | `*-legacy-layout-purge` — delete v1 hardcodes loop/harness |

Brownfield: финальный **s11-legacy-layout-purge** обязателен (sunset A+B+C).

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `5–7` | Resolver+migrate критичны — не резать s05/s10 |
| `cut_list` | `['mb-scaffold audit P2 polish', 'auto scaffold on arm optional']` | Scope trim, не меньше sNN |

---

## Следующий режим

→ BACK DECOMPOSE T-HUB-047-harness-mb-scaffold-epic-layout
