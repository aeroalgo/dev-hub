# [T-HUB-092 | roadmap-cadence-foundation] PLAN

**Дата:** 2026-09-11  
**Режим:** BACK PLAN (multi-epic cut)  
**Уровень:** L3  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `roadmap-cadence-20260911`  
**Deps:** нет (первый в нарезке)  
**Unlocks (queue):** T-HUB-093 → T-HUB-094  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** чат cadence; split mega-plan → foundation / block / resync

---

## Epic cut (нарезка)

| ID | Ось | Deps |
|----|-----|------|
| T-HUB-092 | Foundation: SoT, counter every-2, pause feature-advance | — |
| T-HUB-093 | Block: REPLAN pair → PLAN REFACTOR | T-HUB-092 |
| T-HUB-094 | Tail: reconcile from-queue + resync + Kind I | T-HUB-093 |

**Covering:** одинаковый текст в трёх `md/prompt.md`.

---

## Контекст

- **req:** Typed cadence SoT + счётчик feature done + вход в блок после 2 + запрет армить следующий feature, пока cadence активен. Исполнение REPLAN/Refactor/resync — **не** этот эпик.
- **gap:** `mark_done`/`roadmap_advance` всегда едут в следующий feature; нет kind/counter/phase.
- **refs:** `loop/roadmap_queue.py`, `loop/context_loop.py` EPIC_DONE chain.
- **Не:** REPLAN arm, refactor upsert, reconcile from-queue, sliding window, FRONT/INTEG.

**CREATIVE need:** нет.

---

## Delivery closure

| Capability | Classification | Entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| Cadence SoT | vertical_slice | load/save `cadence.yaml` | invalid → fail-closed | ValidationError on bad phase |
| Feature counter + kind | vertical_slice | `mark_queue_epic_done` | refactor не ++ | pytest kind filter |
| Pause advance | vertical_slice | `roadmap_advance` / select | mid-block feature arm forbidden | after 2 feature done next ≠ third feature |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN |
|-------|---------------|-----------|
| Cadence | pydantic `roadmap-cadence/v1` | prose counter / Handoff-only |
| kind | Literal/enum на queue row; default `feature` | все done считают без kind |
| phase | enum incl. `idle` \| `replan` \| … | soft flag default off |
| Trigger | `every_n: 2` + counter in SoT | env-only без persist |

Foundation **выставляет** `phase=replan` и `pair_ids` при trigger; **не** обязан исполнять REPLAN (это 093). Advance при `phase!=idle` не выбирает новый feature (может вернуть cadence-pending / stop для 093 wire — в 092 достаточно «не feature»; полный arm REPLAN в 093).

---

## Продуктовая спека (WHAT)

1. `memory-bank/back/roadmap/cadence.yaml` + schema validate-on-write.
2. Queue row `kind` (default feature); только feature инкрементит counter.
3. После 2 feature done: `pair_ids` = эта пара, `phase=replan` (блок начат).
4. Пока `phase != idle`: `roadmap_advance` не армает новый feature epic.
5. Идемпотентный mark_done не двойной ++.
6. CLI `cadence-status` (минимум).

### Product probe

Phase 0 skipped — chat lock. Narrowest wedge = SoT+gate only; executors в 093/094.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | Typed cadence load/save | P0 | bad YAML fail-closed |
| US-002 | feature ++ / refactor no ++ | P0 | mark_done matrix |
| US-003 | 2 done → phase replan, pair len 2 | P0 | state after two marks |
| US-004 | mid-block no new feature arm | P0 | advance ≠ third feature |

---

## FR / NFR

| ID | Req |
|----|---------|
| FR-001 | Schema + path cadence.yaml |
| FR-002 | API load/save/on_feature_done/on_non_feature_done |
| FR-003 | kind on queue; default feature |
| FR-004 | Wire mark_done → cadence hook |
| FR-005 | Wire advance: block feature select if phase≠idle |
| FR-006 | Tests + cadence-status CLI |
| FR-007 | Stub hooks/docs pointer: full block in 093/094 (не implement их) |
| NFR-001 | Fail-closed corrupt SoT |
| NFR-002 | Idempotent mark |

---

## Target layout

| Path | Action |
|------|--------|
| `loop/schemas/roadmap_cadence.py` | Create |
| `loop/schemas/__init__.py` | Modify |
| `loop/roadmap_cadence.py` | Create |
| `loop/roadmap_queue.py` | Modify (kind + hooks + gate) |
| `loop/context_loop.py` | Modify (CLI status; EPIC_DONE respects gate) |
| `memory-bank/back/roadmap/cadence.yaml` | Create |
| `loop/tests/test_roadmap_cadence.py` | Create |
| `loop/tests/test_roadmap_queue.py` | Modify |

---

## Replacement / sunset A+B+C+I

| Legacy | Fate |
|--------|------|
| Always advance feature after done | Deny when phase≠idle |
| No kind on rows | default feature; explicit refactor later |
| Optional cadence | FORBIDDEN |

Instruction: краткий pointer в `loop/WORKFLOW.md`; полные REPLAN/Refactor Kind I — в 093/094.

---

## AC+ / AC−

**AC+:** 2 feature done → phase=replan; advance не армает feature; refactor done не ++ counter; tests green targeted.

**AC−:** нет dual-path optional cadence; нет silent old advance; нет реализации REPLAN/Refactor/resync как done этого эпика.

---

## Steps (advisory 5–6)

1. Schema + cadence.yaml + load/save tests  
2. kind + on_feature_done / pair / phase=replan  
3. mark_done wire + idempotency  
4. advance gate  
5. CLI status + docs pointer  
6. Integration: two done → blocked feature arm  

---

## QA consumes draft

| TM | Check |
|----|-------|
| TM-01 | 2 feature done → phase replan |
| TM-02 | third feature not armed |
| TM-03 | refactor kind no counter bump |
| TM-04 | corrupt cadence fail-closed |

## Review readiness

| Item | Status |
|------|--------|
| Split 092/093/094 | Resolved |
| Executors out of 092 | Resolved |
| Gap oracle | Deferred to 093 |

**CREATIVE:** нет.
