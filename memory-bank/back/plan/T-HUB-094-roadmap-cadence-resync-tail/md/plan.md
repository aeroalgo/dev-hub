# [T-HUB-094 | roadmap-cadence-resync-tail] PLAN

**Дата:** 2026-09-11  
**Режим:** BACK PLAN (multi-epic cut)  
**Уровень:** L2–L3  
**Статус:** active  
**Clarify:** Phase 0 skipped — taxonomy clear  
**Prompt:** [md/prompt.md](prompt.md)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `roadmap-cadence-20260911`  
**Deps:** **T-HUB-093** (block exec done → phase resync-ready)  
**Skills:** writing-plans · python-testing-patterns  
**Источник:** чат; ось Tail нарезки cadence

---

## Epic cut (нарезка)

| ID | Ось | Deps |
|----|-----|------|
| T-HUB-092 | Foundation | — |
| T-HUB-093 | REPLAN → Refactor | T-HUB-092 |
| T-HUB-094 | reconcile + resync + resume + Kind I | T-HUB-093 |

---

## Контекст

- **req:** После block (093): reconcile всех ids в `queue:`; при HIGH — resync/invalidate HOW (не §Epic); запрет resume feature до обработки; reset cadence idle; Kind I docs (no sliding window).
- **gap:** reconcile сегодня single/active(tasks.md), не queue tail; нет resume gate после cadence.
- **refs:** `harness/hooks/epic/reconcile.py`, cadence phase from 092/093.
- **Не:** foundation counter; REPLAN/Refactor executors; LLM rewrite prompts.

**CREATIVE need:** нет.

---

## Delivery closure

| Capability | Classification | Entrypoint | Enforcement | Independent test |
|---|---|---|---|---|
| from-queue reconcile | vertical_slice | CLI/API queue ids | reports per queue epic | pytest lists queue ids |
| Resume gate | vertical_slice | cadence resync phase | HIGH without resync → no feature arm | blocked advance |
| Reset idle | vertical_slice | after ok/resync | counter/phase reset | next feature allowed |

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN |
|-------|---------------|-----------|
| Reconcile scope | queue.yaml ids list | only tasks.md active as sole post-cadence check |
| Resync record | structured evidence on cadence SoT | soft ignore HIGH |
| Prompt | §Epic immutable | rewrite Epic in resync |
| Instructions | Kind I update | teach sliding window |

---

## Продуктовая спека (WHAT)

1. `reconcile` mode `--from-queue` / API: iterate `queue:` epic bundles.
2. Cadence phase `resync`: run reconcile; persist summary on SoT.
3. `high_count > 0` без `resync_evidence` → feature advance forbidden.
4. Resync policy: invalidate/mark stale HOW and/or rewrite plan layout paths; **never** mutate prompt §Epic.
5. Success → phase=`idle`, reset feature counter, allow feature advance.
6. Kind I: finish-doc-router / WORKFLOW / mainrule — cadence every-2 REPLAN→Refactor→resync; forbid window.

### User Stories

| # | Story | P | Independent Test |
|---|-------|---|------------------|
| US-001 | from-queue reports | P0 | ids ⊂ queue |
| US-002 | HIGH blocks resume | P0 | advance fail-closed |
| US-003 | after resync idle | P0 | feature arm works |
| US-004 | no window in rules | P0 | rg Kind I |

---

## FR

| ID | Req |
|----|---------|
| FR-001 | reconcile from-queue implementation |
| FR-002 | cadence resync phase + evidence fields |
| FR-003 | resume gate in advance |
| FR-004 | reset API |
| FR-005 | tests |
| FR-006 | Kind I docs/rules |
| FR-007 | optional minimal resync helper (mark plan stale) — full JIT PLAN остаётся agent-side |

---

## Target layout

| Path | Action |
|------|--------|
| `harness/hooks/epic/reconcile.py` | Modify |
| `loop/roadmap_cadence.py` | Modify (resync/reset) |
| `loop/roadmap_queue.py` / `context_loop.py` | Modify (gate + CLI) |
| `loop/tests/test_reconcile_spec.py` | Modify |
| `loop/tests/test_roadmap_cadence.py` | Extend |
| `.cursor/rules/shared/finish-doc-router.mdc` | Modify if needed |
| `loop/WORKFLOW.md` / `loop/README.md` | Modify |
| `.cursor/rules/back_developer/mainrule.mdc` | Modify |

---

## Replacement / sunset

| Legacy | Fate |
|--------|------|
| Post-hygiene no tail check | Deny resume without reconcile path |
| tasks.md-only sweep as cadence exit | Extend with from-queue; не оставлять only-active как единственный exit |

---

## AC+ / AC−

**AC+:** from-queue works; HIGH blocks; reset restores feature lane; rules document cadence without window.

**AC−:** no resume on raw HIGH; no §Epic mutation; no reintroduce window; no re-implement 092/093 executors.

---

## Steps (advisory 5–6)

1. from-queue reconcile + tests  
2. cadence resync phase + evidence  
3. resume gate  
4. reset idle  
5. Kind I docs  
6. E2E: block_done → HIGH → block → resync → feature  

---

## QA consumes draft

| TM | Check |
|----|-------|
| TM-01 | from-queue finds pending queue epic |
| TM-02 | HIGH without resync blocks |
| TM-03 | after reset feature advances |
| TM-04 | Kind I no sliding window |

## Review readiness

| Item | Status |
|------|--------|
| Deps 093 | Required |
| Full auto plan rewrite LLM | Cut — stale mark / path fix only |

**CREATIVE:** нет.
