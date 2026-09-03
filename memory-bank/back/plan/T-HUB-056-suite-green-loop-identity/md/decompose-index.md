# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-056-suite-green-loop-identity  
**План:** [plan/T-HUB-056-suite-green-loop-identity/md/plan.md](../plan/T-HUB-056-suite-green-loop-identity/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-03  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один test-file cluster или один prod-модуль). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 / AC+ arm-stem | arm short id → plan stem в armed_epic / AC | s01 | TM-001 |
| US-002 / FR-002 | prepare fixture + epic_resolve provision | s02 | TM-002 |
| FR-006 | check_after commits next step post-implement | s03 | TM-003 |
| US-003 / FR-004 | drift_counters при valid handoff shape | s04 | TM-004 |
| US-004 / FR-005 | doctor exit codes T-HUB-044 contract | s05 | TM-005 |
| FR-003 | episode finalize в check_after (graceful) | s06 | TM-003 |
| US-005 / FR-007 / SC-006 | full suite 0 failed | s07 | TM-007 |
| FR-001 sunset A/B/C | legacy short-id + fail-open purge | s08 | purge |
| NFR-001 (нет silent doctor exit 0 при real fail) | doctor exit gate не ослаблять | s05 | AC− |

## Stages coverage (plan → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| arm/epic_transition short→stem resolve | plan §До DECOMPOSE s01 | s01 |
| context_loop fixtures + promote path provision | plan §До DECOMPOSE s02 | s02 |
| remaining context_loop check_after/prepare | plan §До DECOMPOSE s03 | s03 |
| drift_display handoff fixtures | plan §До DECOMPOSE s04 | s04 |
| incidents_doctor align T-HUB-044 | plan §До DECOMPOSE s05 | s05 |
| episode_wire | plan §До DECOMPOSE s06 | s06 |
| full suite green gate | plan §До DECOMPOSE s07 | s07 |
| legacy-fallback-purge | plan §До DECOMPOSE s08 | s08 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Loop резолвит epic identity в полный stem (plan-*.md / decompose-* папки) | s01 |
| prepare_session не деградирует при корректных post-041 fixtures | s02, s03 |
| drift_counters присутствуют при valid handoff и nonzero state | s04 |
| doctor дают предсказуемые exit codes на валидном проекте (exit 0, warn 0) | s05 |
| episode finalize в check_after — graceful при RuntimeError | s06 |
| bin/pytest 0 failed (совместно с 054+055) | s07 |
| Нет legacy short-id armed_epic; нет fail-open validate skip | s08 |
| Нет silent doctor exit 0 при реальном fail (AC−) | s05 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| short queue id как armed_epic / AC epic_id | A | plan stem slug | s01, s08 | no | rg verify в s08 |
| pre-041 hardcode hook paths в test fixture | B | harness/hooks + symlink / env | s08 | no | rg verify |
| fail-open validate skip (missing epic_resolve) | C | fail-closed / env gate | s08 | no | rg verify |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-epic-transition-plan-stem-resolve.yaml](s01-epic-transition-plan-stem-resolve.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-context-loop-fixtures-promote-path.yaml](s02-context-loop-fixtures-promote-path.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-context-loop-check-after-remaining.yaml](s03-context-loop-check-after-remaining.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-drift-display-handoff-fixtures.yaml](s04-drift-display-handoff-fixtures.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-incidents-doctor-t-hub-044-align.yaml](s05-incidents-doctor-t-hub-044-align.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-episode-wire-check-after-finalize.yaml](s06-episode-wire-check-after-finalize.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-full-suite-green-gate.yaml](s07-full-suite-green-gate.yaml) | — | no | no | BACK IMPLEMENT | completed |
| **s08** | [s08-legacy-fallback-purge.yaml](s08-legacy-fallback-purge.yaml) | — | no | no | BACK IMPLEMENT | completed |