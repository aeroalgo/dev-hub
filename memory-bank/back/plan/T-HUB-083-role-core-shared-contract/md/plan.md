# T-HUB-083 — Shared role-core contract

**Дата:** 2026-09-07 · **Режим:** BACK PLAN · **Уровень:** L3 · **Статус:** draft
**Clarify:** Phase 0 skipped — common/unique inventory is in audit. **Prompt:** [md/prompt.md](prompt.md)

## WHAT

Extract shared memory-bank loading, response format and hub/managed runner policy from three `mainrule-core.mdc` files. Keep BACK lifecycle/promotion, FRONT visible-UI and parent-only tests, INTEG element-first/contract/gap fanout in compact role cores.

## FR / AC

- **FR-001:** shared core is sole owner of common policy.
- **FR-002:** each role core imports it once and contains only role-only semantics.
- **FR-003:** semantic tests require BACK promotion, FRONT parent-only boundary, INTEG contract fanout and hub/managed branch wording.

1. Common policy changes in one source.
2. Missing import, copied common prose or missing role marker fails.
3. No mode W needs compensating changes.

### AC−

- No generic core replacing role responsibility; no unconditional managed pytest; no weakening lifecycle/UI/contract guards.

## HOW / Eng spine

```text
role/mainrule-core -> shared/role-core-contract -> role-only semantics -> semantic inventory
```

TM-083-01 common import; TM-083-02 no copied body; TM-083-03 BACK lifecycle; TM-083-04 FRONT parent-only; TM-083-05 INTEG contract; TM-083-06 full suite.

## Replacement / sunset

| Kind | Legacy | Replacement | Policy |
|---|---|---|---|
| A | common paragraphs copied in 3 cores | shared core contract | delete in-epic |
| C | core succeeds without shared policy | validation failure | delete in-epic |
| I | duplicate MEMORY BANK/format/runner prose | single shared import | delete in-epic |
| B | n/a | n/a | n/a |

## Review readiness

Product probe, Eng spine, delivery closure and QA matrix: **done**; no pending Required row.

## Draft stages

1. classify/red tests; 2. add shared core/rewire; 3. purge common prose; 4. role fixtures, suite and sunset scan.

## Следующий режим

→ **BACK DECOMPOSE T-HUB-083-role-core-shared-contract**
