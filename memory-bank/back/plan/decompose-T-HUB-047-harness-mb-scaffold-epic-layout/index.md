# Decompose Index — T-HUB-047-harness-mb-scaffold-epic-layout

**Plan:** [plan-T-HUB-047-harness-mb-scaffold-epic-layout.md](../plan-T-HUB-047-harness-mb-scaffold-epic-layout.md)  
**Status canon:** index.yaml  
**Steps:** 12 (s01–s12)

---

## Requirements coverage

| FR / SC / US | Plan FR text (verbatim) | sNN | Notes |
|---|---|---|---|
| FR-001 | Schema `loop/schemas/plan_spec.py` — `epic-plan/v1`: `plan_id`, `level`, `formula?`, `summary{step_count_floor, requirement_count}`, `requirements[]`, `outline_steps[]`, `stages[]`, `sunset_refs[]`, `technology_axiom` | s01 | |
| FR-002 | Schema `loop/schemas/epic_layout.py` — `epic-layout/v2` path kinds: `plan_md`, `plan_yaml`, `decompose_index_md`, `decompose_index_yaml`, `decompose_step`, `implement_step`, `qa_yaml`, `analyze_yaml`, `audit_yaml` | s01 | |
| FR-003 | Module `loop/paths/epic_layout.py` — `resolve(role, epic_id, kind, step_id?) -> Path`; единственный path API для loop + harness (re-export in `harness/hooks/epic_paths.py` thin wrapper) | s02, s06 | |
| FR-004 | Module `loop/mb_scaffold/` — `scaffold_plan`, `scaffold_decompose`, `scaffold_implement_all`, `scaffold_qa`, `scaffold_analyze`, `scaffold_audit`; pydantic request/result models (`mb-scaffold-result/v1`) | s03 | |
| FR-005 | CLI `epic_resolve.py mb-scaffold <subcmd>`: `plan`, `decompose`, `implement`, `qa`, `analyze`, `audit`; flags `--epic-id`, `--force`, `--dry-run`, decompose: `--from-plan`, `--formula` | s04 | |
| FR-006 | Skeleton contract: semantic fields empty (`delta: []`, `as_built: []`, `goal: ""` or placeholder comment block); schema + `step_id` + `plan_refs` pre-filled from `outline_steps.maps_to`; не generic formula goals | s03 | |
| FR-007 | `mb-scaffold plan` writes `md/plan.md` (section headers from template) + `yaml/plan.yaml` (minimal valid spec); operator/agent fills prose in md + enriches yaml on PLAN FINISH | s03, s04 | |
| FR-008 | `mb-scaffold decompose` reads `plan.yaml` outline → steps + index; optional `--formula` merges formula step titles into outline floor only | s03, s09 | |
| FR-009 | Migrate `loop/formula_render.py` output target → resolver paths under `plan/<epic_id>/decompose/yaml/steps/`; deprecate flat `decompose-<id>/` output (purge in s11) | s09, s11 | |
| FR-010 | Migrate script `loop/migrate/epic_layout_v1_to_v2.py` — `--dry-run/--apply`; moves `plan-<id>.md`, `decompose-<id>/` → `plan/<id>/…`; updates internal refs in yaml/md; idempotent | s05 | |
| FR-011 | Loop integration (HARD): `context_loop.py`, `arm_phase`, transition engine, `finalize_step`, parallel orchestrator, board sync, janitor globs — only via `epic_layout.resolve`; zero hardcoded `decompose-*` after purge step | s07 (rewire), s11 (purge gate) | |
| FR-012 | Harness integration (HARD): `epic/core.py`, `reconcile.py`, `session_resilience.py`, `seed_implement`, `mb_finish/*`, `_lib.py` regex — resolver; compat alias for legacy paths until migrate applied (diagnostic `layout_v1_deprecated`) | s06 | |
| FR-013 | Workflow rules (HARD): update `epic-scoped-paths.mdc`, `workflow-{plan,decompose,implement}.mdc`, `memory-bank-paths.mdc`, templates (`epic-step.yaml`), `YAML-CONTRACT.md`, `plan-artifact.md` — document layout v2 + FORBIDDEN Write scaffolded yaml from scratch | s11 | |
| FR-014 | `validate-traceability` — primary inventory from `plan.yaml` `requirements[]`; md fallback удалить in purge step | s08, s11 | |
| FR-015 | `mb-load` (T-HUB-045): bundle paths via resolver when epic ships | s06 | Deferred: T-HUB-045 parallel; s06 exports resolver API |
| FR-016 | session-start / `arm_phase`: optional auto `mb-scaffold <phase>` on phase enter when tree missing (fail-closed if plan invalid) | s12 | |
| FR-017 | Tests: ≥25 pytest covering resolver, scaffold modes, migrate, loop arm smoke, mb-finish path, forbidden agent Write policy | s12 | |
| FR-018 | Hub self-test cwd guard on all mb-scaffold subcommands | s04, s12 | |
| SC-001 | Layout v2 resolver 100% loop hot paths | s02, s07 | pytest `test_epic_layout_resolver_loop_smoke` |
| SC-002 | Migrate all active hub epics dry-run 0 errors | s05, s10 | CLI migrate dry-run on dev-hub memory-bank |
| SC-003 | DECOMPOSE scaffold 5-step epic: agent edit-only | s03 | harness doc gate + manual smoke doc |
| SC-004 | No hardcoded `plan/decompose-` in loop/ after purge | s07, s11 | rg gate pytest |
| SC-005 | validate-traceability reads plan.yaml | s08 | pytest FR coverage |
| US-001 | `plan.yaml` с `outline_steps` и `summary.step_count_floor` — CLI знал минимум задач | s01, s03 | |
| US-002 | `mb-scaffold decompose --from-plan` создал tree до агента; агент только edit fill | s03, s04 | |
| US-003 | Единый path resolver; loop/arm/finish/load не ломались при layout v2 | s02 | |
| US-004 | Migrate script flat→v2 для существующих эпиков | s05 | |
| US-005 | `mb-scaffold implement --all` из decompose index | s03, s04 | |
| US-006 | Phase scaffold из epic context (qa/analyze) | s03, s04 | |
| US-007 | `validate-traceability` читал `plan.yaml` requirements без regex md | s08 | |
| US-008 | DECOMPOSE agent может добавить sNN сверх outline floor при coverage gap | s03 | |

---

## Stages coverage

| Stage (план) | sNN | Outcome |
|---|---|---|
| 1. Schemas (epic-plan/v1, epic-layout/v2) | s01 | pydantic models валидированы |
| 2. Resolver (loop/paths/epic_layout.py) | s02 | `resolve(role, epic_id, kind)` → Path |
| 3. mb_scaffold module (scaffold_plan/decompose/implement_all/qa/analyze/audit) | s03 | skeleton writer, pydantic request/result |
| 4. CLI subparser (mb-scaffold) | s04 | `epic_resolve.py mb-scaffold …` работает |
| 5. Migrate script (v1→v2) | s05 | --dry-run/--apply идемпотентен |
| 6. Harness integration (thin wrapper + mb_finish/seed_implement/reconcile) | s06 | ни одного hardcoded path в harness |
| 7. Loop integration (context_loop/arm_phase/janitor) | s07 | ни одного hardcoded `decompose-*` в loop hot paths |
| 8. validate-traceability из plan.yaml | s08 | md fallback удалён/за guard |
| 9. formula-render merge → mb-scaffold --formula | s09 | formula_render standalone deprecated |
| 10. Migrate apply на dev-hub + smoke | s10 | validate-decompose-tree green после apply |
| 11. Legacy purge (workflow rules + hardcoded globs) | s11 | rg gate пустой на `decompose-*/plan-*.md` в loop/ |
| 12. Tests + session-start arm_phase auto-scaffold | s12 | ≥25 pytest green; FR-016/FR-017 covered |

---

## Outcome map

| AC (plan) | sNN | Measurable verify |
|---|---|---|
| AC-1: `epic-plan/v1` + `epic-layout/v2` pydantic schemas validated on write | s01 | `pytest harness/hooks/tests/test_plan_spec.py -q` exit 0 |
| AC-2: `loop/paths/epic_layout.py` resolver — единственный path source (post-purge) | s02, s07, s11 | `rg 'decompose-' loop/ harness/ --include="*.py" \| grep -v test \| grep -v "#"` → 0 after purge |
| AC-3: `mb-scaffold` CLI: plan, decompose, implement (--all), qa, analyze, audit | s04 | `python harness/hooks/epic_resolve.py mb-scaffold --help` lists all subcommands |
| AC-4: Skeleton contract documented; workflow FORBIDDEN full Write | s03, s11 | `rg 'FORBIDDEN.*Write.*sNN' .cursor/rules/back_developer/workflow-decompose.mdc` → match |
| AC-5: Migrate script v1→v2 + apply on dev-hub memory-bank | s05, s10 | `python harness/hooks/epic_resolve.py mb-migrate --dry-run --cwd $PROJECT_ROOT \| python -c "import sys,json; d=json.load(sys.stdin); assert d['ok'] and not d.get('errors')"` |
| AC-6: Loop + harness integration green: `pytest loop/tests harness/hooks/tests` | s07, s12 | `bin/pytest harness/hooks/tests/ loop/tests/ -q --tb=short` exit 0 |
| AC-7: `validate-traceability` plan.yaml primary | s08 | `bin/pytest harness/hooks/tests/test_validate_traceability.py::test_yaml_primary_missing_fr -q` exit 0; `rg 'md_fallback\|parse_plan_md' harness/hooks/validate_traceability.py \| wc -l \| grep -E '^0$'` |
| AC-8: formula-render merged into mb-scaffold decompose (--formula) | s09 | `bin/pytest harness/hooks/tests/test_mb_scaffold_decompose.py::test_formula_merge -q` exit 0; `rg "f'decompose-" loop/formula_render.py \| wc -l \| grep -E '^0$'` |
| AC-9: Legacy path purge (no dual glob in loop/) | s11 | `bin/pytest harness/hooks/tests/test_no_hardcoded_paths.py::test_no_decompose_hardcoded -q` exit 0 |

---

## Replacement cleanup

**Brownfield — непустой deletes у шагов cutover:**

| Путь / символ | Вытесняется в | sNN (deletes owner) | rg verify |
|---|---|---|---|
| `harness/hooks/epic_paths.py` — glob `decompose-*/index.yaml`, `decompose-*/index.md`, `f'decompose-{epic_id}'`, `plan-*.md` glob | resolver | s06 | `rg 'decompose-' harness/hooks/epic_paths.py \| grep -v "#\|deprecated" \| wc -l \| grep "^0"` |
| `harness/hooks/_lib.py` — regex `plan/decompose-\|implement/implement-` | resolver | s06 | `rg 'plan/decompose-\|implement/implement-' harness/hooks/_lib.py \| wc -l \| grep "^0"` |
| `harness/hooks/epic/core.py` + `reconcile.py` + `session_resilience.py` — path строки | resolver | s06 | `rg 'decompose-\|implement-' harness/hooks/epic/ harness/hooks/session_resilience.py \| grep -v "#\|deprecated" \| wc -l \| grep "^0"` |
| `loop/context_loop.py:316,325` — glob `decompose-*/index.md`, regex `plan/decompose-\|implement/implement-` | resolver | s07 | `rg 'decompose-' loop/context_loop.py \| grep -v "#\|deprecated" \| wc -l \| grep "^0"` |
| `loop/janitor/janitor.py` — hardcoded `decompose-*` globs | resolver | s07 | `rg 'decompose-' loop/janitor/ \| grep -v "#\|deprecated" \| wc -l \| grep "^0"` |
| `loop/formula_render.py` — standalone output target к flat `decompose-<id>/` | mb-scaffold --formula | s09, s11 | `rg "f'decompose-" loop/formula_render.py \| wc -l \| grep "^0"` |
| `loop/mb_finish/*` — hardcoded decompose/implement path строки | resolver | s06 | `rg "'decompose-\|'implement-" loop/mb_finish/ \| grep -v "#\|deprecated" \| wc -l \| grep "^0"` |
| `.cursor/rules/ workflow-*.mdc` + `epic-scoped-paths.mdc` — v1 path refs `decompose-{id}/`, `plan-{id}.md` | layout v2 docs | s11 | `rg 'decompose-\{id\}\|plan-\{id\}' .cursor/rules/ \| wc -l \| grep "^0"` |
| `memory-bank-paths.mdc` + `plan-artifact.md` — v1 path refs `decompose-<id>/`, `plan-<id>.md` | layout v2 docs | s11 | `rg 'decompose-[A-Za-z0-9]' .cursor/rules/shared/memory-bank-paths.mdc harness/claude/rules/plan-artifact.md \| wc -l \| grep "^0"` |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | epic-plan/v1 schema + epic-layout/v2 schema (loop/schemas/) · [yaml](s01-plan-spec-schema.yaml) | BACK IMPLEMENT | completed |
| **s02** | loop/paths/epic_layout.py resolver — единственный path API · [yaml](s02-epic-layout-resolver.yaml) | BACK IMPLEMENT | pending |
| **s03** | loop/mb_scaffold/ — scaffold_plan, scaffold_decompose, scaffold_implement_all, scaffold_qa, scaffold_analyze, scaffold_audit · [yaml](s03-mb-scaffold-core.yaml) | BACK IMPLEMENT | pending |
| **s04** | epic_resolve.py mb-scaffold subparser — plan/decompose/implement/qa/analyze/audit · [yaml](s04-mb-scaffold-cli.yaml) | BACK IMPLEMENT | pending |
| **s05** | loop/migrate/epic_layout_v1_to_v2.py — flat→v2 migrate (--dry-run/--apply) · [yaml](s05-migrate-script.yaml) | BACK IMPLEMENT | pending |
| **s06** | Harness integration — epic_paths.py thin wrapper + _lib.py/reconcile.py/seed_implement/mb_finish resolver wire · [yaml](s06-harness-resolver-wire.yaml) | BACK IMPLEMENT | pending |
| **s07** | Loop integration — context_loop/arm_phase/finalize_step/janitor → resolver only (zero hardcoded paths) · [yaml](s07-loop-resolver-wire.yaml) | BACK IMPLEMENT | pending |
| **s08** | validate-traceability primary inventory from plan.yaml (удалить md fallback) · [yaml](s08-validate-traceability-yaml.yaml) | BACK IMPLEMENT | pending |
| **s09** | formula-render merged into mb-scaffold decompose --formula (deprecate standalone) · [yaml](s09-formula-render-merge.yaml) | BACK IMPLEMENT | pending |
| **s10** | Migrate apply на dev-hub memory-bank + validate-decompose-tree green · [yaml](s10-migrate-apply-dev-hub.yaml) | BACK IMPLEMENT | pending |
| **s11** | Legacy path purge — удалить hardcoded decompose-*/plan-*.md glob в loop/ + harness/ + workflow rules update · [yaml](s11-legacy-path-purge.yaml) | BACK IMPLEMENT | pending |
| **s12** | ≥25 pytest + session-start arm_phase auto-scaffold + FR-017 coverage · [yaml](s12-tests-session-start-wire.yaml) | BACK IMPLEMENT | pending |
