# Roadmap: active epics (merged canon)

**Роль:** BACK
**Назначение:** единая очередь для loop (`EPIC_CHAIN_ROADMAP` / `roadmap-advance`).
**Machine queue:** [`roadmap-epics.queue.yaml`](roadmap-epics.queue.yaml)
**Команда:** `BACK ROADMAP MERGE`

Slug-roadmap (`roadmap-<slug>-epics.*`) — источники; этот файл — канон.

---

## Источники

- `memory-bank/back/plan/roadmap-workflow-loop-hardening-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-speckit-workflow-boost-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-loop-observability-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-dsh-mb-board-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-epic-transition-engine-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-spec-maturity-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-dsh-loop-backend-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-back-plan-gstack-adapt-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-pydantic-reliability-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-phase-verify-agents-runtime-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-harness-maturity-borrowings-epics.queue.yaml`

## Пропущены (done)

- `T-HUB-027`
- `T-HUB-029`
- `T-HUB-030`
- `T-HUB-031`
- `T-HUB-032`
- `T-HUB-033`
- `T-HUB-023`
- `T-HUB-034`
- `T-HUB-035`
- `T-HUB-002`
- `T-HUB-003`
- `T-HUB-004`
- `T-HUB-005`
- `T-HUB-010`
- `T-HUB-011`
- `T-HUB-012`
- `T-HUB-013`
- `T-HUB-017`
- `T-HUB-018`
- `T-HUB-014`
- `T-HUB-015`
- `T-HUB-019`
- `T-HUB-020`
- `T-HUB-024`
- `T-HUB-025`
- `T-HUB-026`
- `T-HUB-006`
- `T-HUB-007`
- `T-HUB-016`
- `T-HUB-008`
- `T-HUB-009`

## Очередь

| # | ID | План | Hard deps |
|---|----|------|-----------|
| 1 | T-HUB-039 | [plan-T-HUB-039-phase-verify-agents-runtime.md](plan-T-HUB-039-phase-verify-agents-runtime.md) | — |
| 2 | T-HUB-036 | [plan-T-HUB-036-harness-decompose-formulas.md](plan-T-HUB-036-harness-decompose-formulas.md) | — |
| 3 | T-HUB-037 | [plan-T-HUB-037-harness-parallel-snn.md](plan-T-HUB-037-harness-parallel-snn.md) | — |
| 4 | T-HUB-038 | [plan-T-HUB-038-harness-metrics-dashboard.md](plan-T-HUB-038-harness-metrics-dashboard.md) | — |
| 5 | T-HUB-040 | [plan-T-HUB-040-harness-workflow-finish-api.md](plan-T-HUB-040-harness-workflow-finish-api.md) | — |

## Handoff

- Loop читает **только** `roadmap-epics.queue.yaml` (default path).
- `BACK PLAN` **сам** вызывает `roadmap-merge` в той же сессии (не отдельный next `BACK ROADMAP MERGE`).
- Next: `BACK DECOMPOSE` первого id из queue.
- Ручной `BACK ROADMAP MERGE` — только если канон устарел без PLAN.
