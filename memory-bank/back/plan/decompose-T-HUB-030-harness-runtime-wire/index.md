# decompose-T-HUB-030-harness-runtime-wire / index.md

**Plan:** [plan-T-HUB-030-harness-runtime-wire.md](../plan-T-HUB-030-harness-runtime-wire.md)  
**Role:** BACK  
**Status tracker (canon):** [index.yaml](index.yaml)  
**Дата:** 2026-08-31  

---

## Outcome map (plan → steps)

| Outcome | Зачем | sNN |
|---------|-------|-----|
| `loop doctor` работает до автопилота — operator видит blockers заранее | US-001, SC-001: fail-closed preflight | s01 |
| `check_after` вызывает tier0 auto-repair; success → continue, exhausted → tier1 flag | US-002, US-003: self-healing runtime | s02 |
| `incident-status` / `incident-retry` для ручного ops | US-004: incident lifecycle control | s03 |
| `implement_done`, `phase_transition`, traceability events в events.jsonl | US-005: полный lifecycle timeline | s04 |
| Traceability ON по умолчанию на DECOMPOSE promote; opt-out env=0 | US-006: ранний drift catch | s05 |
| README + optional loop.sh doctor preflight | FR-003, AC#6: documented operator path | s06 |

---

## Requirements coverage

| Requirement | ID | sNN | Status |
|-------------|-----|-----|--------|
| Doctor subparser + delegate run_doctor | FR-001, FR-002 | s01 | pending |
| bin/loop doctor passthrough | FR-002 | s01 | pending |
| loop.sh doctor preflight opt-in | FR-003 | s06 | pending |
| tier0 wire in check_after | FR-004 | s02 | pending |
| Response fields tier0_* / repair_exhausted | FR-005 | s02 | pending |
| repair_applied / incident_resolved events | FR-006 | s02 | pending |
| halt_logic integration on tier0 success | FR-007 | s02 | pending |
| incident-status subparser | FR-008 | s03 | pending |
| incident-retry subparser | FR-009 | s03 | pending |
| EVENT_KINDS extend (5 kinds) | FR-010 | s04 | pending |
| implement_done + phase_transition emit | FR-011 | s04 | pending |
| reconcile backfill new kinds | FR-012 | s04 | pending |
| strict validation test new kinds only | FR-013 | s04 | pending |
| traceability default ON promote | FR-014 | s05 | pending |
| project.env comment opt-out | FR-015 | s05 | pending |
| integration test drift blocks promote | FR-016 | s05 | pending |
| doctor CLI (AC#1) | AC-1 | s01 | pending |
| tier0 wire tests green (AC#2) | AC-2 | s02 | pending |
| incident CLI tests (AC#3) | AC-3 | s03 | pending |
| lifecycle events (AC#4) | AC-4 | s04 | pending |
| traceability default (AC#5) | AC-5 | s05 | pending |
| README observability (AC#6) | AC-6 | s06 | pending |
| doctor healthy fixture | SC-001 | s01 | pending |
| tier0 wire tests | SC-002 | s02 | pending |
| incident CLI smoke | SC-003 | s03 | pending |
| implement_done after finalize | SC-004 | s04 | pending |
| traceability blocks drift promote | SC-005 | s05 | pending |
| US-001 operator doctor | US-001 | s01 | pending |
| US-002 tier0 auto-repair | US-002 | s02 | pending |
| US-003 tier0 exhausted → tier1 | US-003 | s02 | pending |
| US-004 incident ops CLI | US-004 | s03 | pending |
| US-005 lifecycle timeline | US-005 | s04 | pending |
| US-006 traceability ON promote | US-006 | s05 | pending |

---

## Stages coverage

| Plan stage / touch map | sNN |
|------------------------|-----|
| Doctor CLI + tests | s01 |
| tier0 block in check_after | s02 |
| incident-status + incident-retry | s03 |
| epic_events EVENT_KINDS + finalize_step emit | s04 |
| traceability default + project.env | s05 |
| loop/README.md + loop.sh preflight | s06 |
| Full pytest loop/tests regression (AC#7) | s06 cp3 |

---

## Replacement cleanup

| Устаревает | Замена | sNN | Policy |
|-----------|--------|-----|--------|
| n/a | n/a | — | greenfield — wire debt closure; нет sunset A/B/C |

---

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Doctor subcommand — preflight blockers · [yaml](s01-doctor-cli-subcommand.yaml) | BACK IMPLEMENT | completed |
| **s02** | Tier0 auto-repair in check_after · [yaml](s02-tier0-wire-check-after.yaml) | BACK IMPLEMENT | completed |
| **s03** | Incident-status / incident-retry CLI · [yaml](s03-incident-status-retry-cli.yaml) | BACK IMPLEMENT | completed |
| **s04** | Lifecycle EVENT_KINDS + emit hooks · [yaml](s04-lifecycle-event-kinds-emit.yaml) | BACK IMPLEMENT | completed |
| **s05** | Traceability default ON promote · [yaml](s05-traceability-default-promote.yaml) | BACK IMPLEMENT | completed |
| **s06** | README + loop.sh doctor preflight · [yaml](s06-readme-loop-sh-preflight-docs.yaml) | BACK IMPLEMENT | completed |