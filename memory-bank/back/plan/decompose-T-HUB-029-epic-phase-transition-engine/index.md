# decompose-T-HUB-029-epic-phase-transition-engine / index.md

**Plan:** [plan-T-HUB-029-epic-phase-transition-engine.md](../plan-T-HUB-029-epic-phase-transition-engine.md)  
**Role:** BACK  
**Status tracker (canon):** [index.yaml](index.yaml)  
**Дата:** 2026-08-31  

---

## Outcome map (plan → steps)

| Outcome | Зачем | sNN |
|---------|-------|-----|
| `loop/epic_transition.py` — единый Transition Engine API: `resolve_next` + `arm_phase` + `promote_if_ready` | Любой entry point проходит один контракт; дрейф архитектурно невозможен | s01, s02, s03 |
| После DECOMPOSE FINISH с analyze-gate=required → автоматически Handoff ANALYZE (не IMPLEMENT) | US-001: IMPLEMENT не стартует без analyze-*.yaml; fail-closed гарантия | s03, s04 |
| `arm_epic` + `arm_roadmap_entry` + `finalize_step` → `promote_if_ready` post-queue | US-002: board Run и roadmap arm ведут себя как loop prepare; единая истина | s05 |
| `phase_registry.yaml` + `load_phase_registry()` + registry-driven `gates_from_phase` | US-003: finish gate и verify agent из одной таблицы; unknown phase fail-closed | s06 |
| Aliases `verify` → `verify-implement`, `reviewer` → `verify-qa`; `get_verify_agent(phase)` | US-004/005: IMPLEMENT @verify-implement; BACK QA @verify-qa; T-HUB-028 merge | s07 |
| stop-gate + agent-pretool registry-driven (gates + verify_agent из registry) | NFR-2: нет hardcoded gate names в hooks | s08 |
| DSH presets per phase (T-HUB-008 integration); `get_dsh_preset(phase)` | US-006: DSH runtime получает preset из registry; неизвестный preset fail-closed | s09 |
| `_arm_dag_next` DAG adapter → Transition Engine | US-007: DAG scheduler не rewritten; adapter делегирует resolve_next + arm_phase | s10 |
| FRONT/INTEG parity v1: `roles=[back, front, integration]`; role-aware arm_phase | US-008/Q5=B: FRONT DECOMPOSE → FRONT ANALYZE gate; INTEG IMPLEMENT path | s11 |
| Legacy sunset: promote_decompose_phase_if_ready/arm_active_context_from_decompose bodies deleted; WORKFLOW.md + README + architecture shard | NFR-1: нет живых callers deprecated funcs; документация актуальна | s12 |

---

## Requirements coverage

| Requirement | ID | sNN | Status |
|-------------|-----|-----|--------|
| Единый Transition Engine API (resolve_next/arm_phase/promote_if_ready) | FR-001, FR-002 | s01, s02 | pending |
| promote_if_ready: ANALYZE gate enforce перед IMPLEMENT | FR-003, FR-004 | s03, s04 | pending |
| arm_epic + roadmap + finalize_step wired | FR-005, FR-006 | s05 | pending |
| phase_registry.yaml + load_phase_registry + unknown fail-closed | FR-010, FR-011 | s06 | pending |
| get_verify_agent per phase + aliases | FR-007, FR-008 | s07 | pending |
| stop-gate registry-driven gates | FR-009 | s08 | pending |
| sync_cursor ANALYZE pending → no-op rearm | FR-014 | s04 | pending |
| DSH preset per phase (T-HUB-008) | FR-002 (DSH branch) | s09 | pending |
| FRONT/INTEG parity v1 | NFR-3 | s11 | pending |
| Legacy purge + docs | NFR-1, NFR-2 | s12 | pending |
| US-001 DECOMPOSE → ANALYZE gate | US-001 | s03, s04 | pending |
| US-002 board/roadmap/loop parity | US-002 | s05 | pending |
| US-003 phase registry | US-003 | s06 | pending |
| US-004 @verify-implement | US-004 | s07 | pending |
| US-005 @verify-qa BLOCKED→FINISH | US-005 | s07 | pending |
| US-006 DSH presets | US-006 | s09 | pending |
| US-007 DAG adapter | US-007 | s10 | pending |
| US-008 FRONT/INTEG parity | US-008 | s11 | pending |

---

## Stages coverage (plan outline → shards)

| Plan outline stage | sNN |
|--------------------|-----|
| `epic_transition.py` skeleton + `resolve_next` delegate + tests | s01 |
| `arm_phase` unify analyze/decompose/pre-implement handoffs | s02 |
| `promote_if_ready` replace decompose promote; ANALYZE promote | s03 |
| resolver stale analyze; `sync_cursor` registry skip | s04 |
| wire `arm_epic`, `roadmap_queue`, `finalize_step` post-queue | s05 |
| `phase_registry.yaml` + loader + `gates_from_phase` registry-driven | s06 |
| verify agents registry (verify-implement/bugfix/decompose/qa) + aliases | s07 |
| stop-gate + agent-pretool/subagent-stop registry-driven | s08 |
| DSH presets + epic-gate mapping (T-HUB-008 integration) | s09 |
| DAG adapter `_arm_dag_next` → transition engine | s10 |
| FRONT/INTEG parity tests + arm paths | s11 |
| legacy sunset purge + docs (`WORKFLOW.md`, README, architecture) | s12 |

---

## Replacement cleanup

| Устаревает | Замена | sNN deletes | Policy |
|-----------|--------|-------------|--------|
| `promote_decompose_phase_if_ready` body | `promote_if_ready` | s03 (body), s12 (shim remove) | shim+delegate s03 → delete in s12 |
| `arm_active_context_from_decompose` body | `arm_phase(DECOMPOSE)` | s02 (body), s12 (shim remove) | shim+delegate s02 → delete in s12 |
| `arm_pre_implement_context` body | `arm_phase(IMPLEMENT)` | s02 (body), s12 (shim remove) | shim+delegate s02 → delete in s12 |
| `roadmap_queue._arm_analyze_context` public | `epic_transition._arm_analyze_context` (private) | s12 audit | delete or privatise in s12 |
| hardcoded gates dict in `gates_from_phase` | `load_phase_registry` lookup | s06 deletes | inline body replaced |
| hardcoded `@verify` / `@reviewer` in agent-pretool | `get_verify_agent(phase)` | s07/s08 | replaced in hook |
| T-HUB-028 separate implement tree | merged into T-HUB-029 | s07 (aliases) | supersede plan |

---

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | epic_transition.py skeleton + resolve_next delegate + tests — Transition Engine API contract · [yaml](s01-epic-transition-skeleton.yaml) | BACK IMPLEMENT | done |
| **s02** | arm_phase unify analyze/decompose/pre-implement handoffs — shim + delegate · [yaml](s02-arm-phase-unify-handoffs.yaml) | BACK IMPLEMENT | completed |
| **s03** | promote_if_ready + ANALYZE gate enforce — decompose→ANALYZE, не IMPLEMENT · [yaml](s03-promote-if-ready-analyze-gate.yaml) | BACK IMPLEMENT | completed |
| **s04** | resolver stale-analyze guard + sync_cursor IMPLEMENT skip — FR-004, FR-014 · [yaml](s04-resolver-stale-analyze-sync-skip.yaml) | BACK IMPLEMENT | completed |
| **s05** | wire arm_epic + roadmap_queue + finalize_step → promote_if_ready — US-002 entry points · [yaml](s05-wire-arm-epic-roadmap-finalize.yaml) | BACK IMPLEMENT | completed |
| **s06** | phase_registry.yaml + load_phase_registry + gates_from_phase registry-driven — US-003 · [yaml](s06-phase-registry-yaml-loader.yaml) | BACK IMPLEMENT | completed |
| **s07** | verify agents registry + aliases verify→verify-implement, reviewer→verify-qa — US-004/005, T-HUB-028 merge · [yaml](s07-verify-agents-registry-aliases.yaml) | BACK IMPLEMENT | completed |
| **s08** | stop-gate + agent-pretool registry-driven gates — NFR-2 · [yaml](s08-stop-gate-registry-driven.yaml) | BACK IMPLEMENT | completed |
| **s09** | DSH presets + epic-gate mapping T-HUB-008 — get_dsh_preset per phase · [yaml](s09-dsh-presets-epic-gate-mapping.yaml) | BACK IMPLEMENT | completed |
| **s10** | DAG adapter _arm_dag_next → Transition Engine — adapter not rewrite · [yaml](s10-dag-adapter-arm-dag-next.yaml) | BACK IMPLEMENT | completed |
| **s11** | FRONT/INTEG parity v1: role-aware arm paths + registry roles — US-008 · [yaml](s11-front-integ-parity-arm-paths.yaml) | BACK IMPLEMENT | completed |
| **s12** | legacy sunset purge + WORKFLOW.md + README + architecture shard — final cleanup · [yaml](s12-legacy-sunset-purge-docs.yaml) | BACK IMPLEMENT | completed |