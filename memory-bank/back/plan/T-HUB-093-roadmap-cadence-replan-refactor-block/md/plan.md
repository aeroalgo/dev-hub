# [T-HUB-093 | roadmap-cadence-replan-refactor-block] PLAN

**Дата:** 2026-09-11  
**Режим:** BACK PLAN (multi-epic cut)  
**Уровень:** L3  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `roadmap-cadence-20260911`  
**Deps:** **T-HUB-092** (cadence SoT + pause)  
**Unlocks:** T-HUB-094  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** чат; ось Block нарезки cadence

---

## Epic cut (нарезка)

| ID | Ось | Deps |
|----|-----|------|
| T-HUB-092 | Foundation | — |
| T-HUB-093 | REPLAN → PLAN REFACTOR | T-HUB-092 |
| T-HUB-094 | resync tail | T-HUB-093 |

---

## Контекст

- **req:** На живом cadence SoT (092): выполнить фазу REPLAN по `pair_ids` (critical-only, same id, skip+evidence), затем фазу PLAN REFACTOR (новый epic `kind: refactor` или noop). Порядок жёсткий.
- **gap:** после 092 блок «зависнет» в phase=replan без executor.
- **refs:** `loop/roadmap_cadence.py` (092), `workflow-replan.mdc`, `workflow-plan-refactor.mdc`, `roadmap_upsert_batch`.
- **Не:** создание SoT/counter; reconcile from-queue; sliding window; carry steps в соседа.

**CREATIVE need:** нет.

---

## Delivery closure

| Capability | Classification | Entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| REPLAN pair drive | vertical_slice | cadence advance in phase=replan | cannot enter refactor early | order test |
| Critical skip | vertical_slice | gap evidence API | empty critical → skip recorded | no silent empty without evidence |
| Refactor insert/arm | vertical_slice | after replan closed | kind=refactor XOR noop | queue/head assertion |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN |
|-------|---------------|-----------|
| Phase transitions | enum on cadence SoT | refactor while replan open |
| Gap result | structured evidence (list + provenance) | always-skip without write |
| Refactor | queue epic kind=refactor + arm PLAN REFACTOR | steps in neighbor feature |
| One-hop | per id ≤ one replan in block | replan→replan |

Gap oracle MVP: explicit recorder — critical list from checklist/helper **или** NEED_HUMAN; **FORBIDDEN** вечный auto-skip без evidence.

---

## Продуктовая спека (WHAT)

1. При phase=replan loop/arm ведёт REPLAN для каждого id в pair (последовательно): closed или skipped_with_evidence.
2. Critical-only; cosmetic не создаёт работу.
3. Оба id закрыты → phase=refactor.
4. phase=refactor: upsert/arm PLAN REFACTOR epic в голову **или** noop evidence → phase готов к resync (`resync` или эквивалент «block_exec_done» для 094).
5. Попытка refactor API до конца replan → fail-closed.
6. Kind I: `workflow-replan.mdc` / `workflow-plan-refactor.mdc` — cadence order; forbid window/carry.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | REPLAN arms/skips pair ids | P0 | both ids terminal before refactor |
| US-002 | refactor blocked early | P0 | error if phase=replan |
| US-003 | refactor epic or noop | P0 | kind refactor XOR noop evidence |
| US-004 | no neighbor carry steps | P0 | AC− / rg policy in rules |

---

## FR

| ID | Req |
|----|---------|
| FR-001 | `advance_replan` / record skip|complete per pair id |
| FR-002 | transition to refactor only when pair done |
| FR-003 | `start_refactor_phase` upsert+arm or noop |
| FR-004 | mark refactor epic done → handoff phase for 094 (resync) |
| FR-005 | Wire roadmap_advance to arm REPLAN/PLAN REFACTOR commands via activeContext identity |
| FR-006 | Tests order + skip evidence |
| FR-007 | Kind I workflows replan + plan-refactor |

---

## Target layout

| Path | Action |
|------|--------|
| `loop/roadmap_cadence.py` | Modify (replan/refactor transitions) |
| `loop/roadmap_queue.py` | Modify (upsert refactor kind; advance arms) |
| `loop/context_loop.py` | Modify (arm command identity for REPLAN/PLAN REFACTOR) |
| `loop/workflow/command_router.py` | Modify if REPLAN route missing |
| `loop/tests/test_roadmap_cadence.py` | Extend |
| `.cursor/rules/back_developer/workflow-replan.mdc` | Modify |
| `.cursor/rules/back_developer/workflow-plan-refactor.mdc` | Modify |
| `.cursor/rules/back_developer/mainrule.mdc` | Modify (cadence block pointer) |

---

## Replacement / sunset

| Legacy | Fate |
|--------|------|
| Manual-only REPLAN with no loop order | Wire into cadence phases |
| Refactor anytime | Deny before replan closed |
| Window / carry-to-neighbor as канон | FORBIDDEN in Kind I |

---

## AC+ / AC−

**AC+:** cannot arm refactor in replan; after pair skip/complete → refactor or noop; tests enforce order; rules state REPLAN→Refactor.

**AC−:** no refactor-before-replan path; no replan-of-replan; no carry FR steps; no implementing from-queue resync here (094).

---

## Steps (advisory 5–7)

1. Gap evidence model + skip/complete API  
2. Drive replan phase for pair ids (arm/test doubles)  
3. Gate refactor-until-replan-done  
4. Upsert/arm refactor epic + kind  
5. Noop path + phase → resync-ready  
6. command_router REPLAN if needed  
7. Kind I workflows + tests  

---

## QA consumes draft

| TM | Check |
|----|-------|
| TM-01 | refactor before replan done → fail |
| TM-02 | both skipped → noop refactor allowed |
| TM-03 | refactor kind not counted as feature (092 invariant still holds) |
| TM-04 | rules forbid window/carry |

## Review readiness

| Item | Status |
|------|--------|
| Depends 092 | Required — queue deps |
| Gap oracle detail | DECOMPOSE: evidence XOR NEED_HUMAN |
| Resync | Out → 094 |

**CREATIVE:** нет.
