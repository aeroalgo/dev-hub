# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-057-loop-session-json-contract  
**План:** [plan/T-HUB-057-loop-session-json-contract/md/plan.md](../plan/T-HUB-057-loop-session-json-contract/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-03  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Session start → MbLoadResult; fail-closed при shape invalid | s02 | |
| FR-002 | prepare/build_prompt: primary = mb-load | s02 | |
| FR-003 | Boundary registry: schema_id + pydantic model; validate-before-accept | s01, s03 | |
| FR-003a | validate_boundary(schema_id, payload) → ValidateResult; CLI epic_resolve.py | s03 | |
| FR-003b | Pre-emit и boundary hook — один helper; dual checker FORBIDDEN | s03 | |
| FR-004 | Schema-retry на boundary accept; N=2 gate / N=1 repair; escalate NEED_HUMAN | s03, s06 | |
| FR-005 | Error taxonomy schema vs semantic vs finish vs loop | s03, s04 | |
| FR-006 | Semantic FAIL → repair; PreToolUse DENY repair без FAIL | s04 | |
| FR-007 | PASS → mb-finish hint; stop-gate требует last_finish_tool fingerprint | s06 | |
| FR-008 | mb-finish-result/v1: finished_step + next_step/next_phase/epic_done | s05 | |
| FR-009 | Post-finish: next_identity != finished_step; loop_* fail-closed иначе | s05 | |
| FR-010 | extract_verdict / stop-gate: JSON+sidecar only; prose VERDICT не machine | s03, s07 | TM-010 |
| FR-011 | Epic state: fingerprint, schema_retry counters, last_finish_tool, last_finished_step, armed_after_finish | s05, s06 | |
| FR-012 | Phase matrix IMPLEMENT P0; QA/ANALYZE/DECOMPOSE P1 same protocols | s07 | P1 coverage |
| FR-013 | Purge dual prose START/FINISH instructions in loop prompts | s08 | |
| FR-014 | Pytest: TM matrix (TM-001..011) | s07 | |
| FR-015 | Out of scope: Codex (053), pack (050), board (055), mid-turn JSON | — | out_of_scope |
| AC+ SC-001 | mb-load primary START | s02 | |
| AC+ SC-002 | schema-invalid ≠ PASS; retry then NEED_HUMAN | s03, s06 | |
| AC+ SC-003 | semantic FAIL → repair, not schema-retry | s04 | |
| AC+ SC-004 | PASS → mb-finish required | s06 | |
| AC+ SC-005 | finish next ≠ finished | s05 | |
| AC+ SC-006 | re-arm same step fail-closed | s05 | |
| AC+ SC-007 | no prose VERDICT machine path | s08, s07 | |
| AC− prose dual path | prose START/FINISH как primary SoT — удалить | s08 | purge |
| AC− dual checker | два разных validate helper — FORBIDDEN | s03, s08 | |
| US-001 | mb-load primary SoT | s02 | |
| US-003b | SubagentStop re-validate даже после pre-emit ok | s03 | |
| US-005 | semantic FAIL → repair path, не schema-retry | s04 | |
| US-008 | fail-closed если arm/next == только что закрытый step | s05 | |
| NFR latency | boundaries at JSON fence; no regex salvage | s03 | |
| NFR traceability | epic state: fingerprint + counters persist | s06, s05 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Inventory gaps + registry draft | plan §Decompose input map s01 | s01 |
| B-START boundary wiring (prepare → MbLoadResult) | plan §Boundaries B-START / FR-001/002 | s02 |
| B-GATE boundary: validate_boundary + schema-retry (verify/reviewer/analyze-verify) | plan §Boundaries B-GATE / FR-003/003a/003b/004 | s03 |
| B-REPAIR boundary: repair path + taxonomy fork (gate-repair emit → SubagentStop) | plan §Boundaries B-REPAIR / FR-005/006 | s04 |
| B-ARM boundary: mb-finish-result/v1 typed next_* + anti-loop guard | plan §Boundaries B-ARM / FR-008/009 | s05 |
| stop-gate fingerprint + NEED_HUMAN escalation (schema exhausted) | plan §Boundaries / FR-007/011 / SC-004 | s06 |
| pytest TM-001..011 full suite | plan §Test matrix FR-014 | s07 |
| Prose sunset purge (FR-013 AC−) | plan §Technology axiom / FR-013 | s08 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Один machine path сессии: mb-load → validate → gate → repair → finish → arm next≠finished | s01, s02, s03, s04, s05, s06 |
| Schema fail → same-agent retry (≤N); после N → NEED_HUMAN; без silent accept | s03, s06 |
| Semantic FAIL строго отделён от schema fail; repair path не пересекает schema-retry | s03, s04 |
| PASS → mb-finish обязателен; stop-gate requires fingerprint | s06 |
| finish result typed: finished_step + next discriminant; arm проверяет next ≠ finished | s05 |
| Anti-loop: arm того же sNN fail-closed с step_loop_forbidden | s05 |
| Epic state полный: fingerprint, counters, last_finished_step, armed_after_finish | s05, s06 |
| Все TM-001..011 P0 покрыты behavior tests | s07 |
| Prose START/FINISH instructions purged; нет dual-checker shim | s08 |
| Out of scope: Codex (053), pack (050), board (055), mid-turn JSON every message | — follow-up |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| loop/loop.sh — prose SESSION START/FINISH blocks | A | mb-load / mb-finish calls | s08 | no | inline purge |
| loop/context_loop.py — prose build_prompt instructions | A | MbLoadResult primary path | s08 | no | inline purge |
| dual validate helper shim (если возник при s03) | A | loop/validate_boundary.py unified | s08 | no | FR-003b; s08 deletes any shim found |

> **Brownfield purge:** s08 = `*-legacy-fallback-purge`; sunset_inventory scan в s08 checkpoints.

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-inventory-gaps-registry-draft.yaml](s01-inventory-gaps-registry-draft.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-session-start-mb-load-primary.yaml](s02-session-start-mb-load-primary.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-validate-boundary-schema-retry.yaml](s03-validate-boundary-schema-retry.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-semantic-fail-repair-taxonomy.yaml](s04-semantic-fail-repair-taxonomy.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-mb-finish-next-arm-anti-loop.yaml](s05-mb-finish-next-arm-anti-loop.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-stop-gate-finish-fingerprint-need-human.yaml](s06-stop-gate-finish-fingerprint-need-human.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-pytest-tm-matrix.yaml](s07-pytest-tm-matrix.yaml) | — | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-prose-path-legacy-fallback-purge.yaml](s08-prose-path-legacy-fallback-purge.yaml) | — | no | yes | BACK IMPLEMENT | completed |