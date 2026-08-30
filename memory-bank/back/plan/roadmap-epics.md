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
- `memory-bank/back/plan/roadmap-dsh-loop-backend-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-pydantic-reliability-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-spec-maturity-epics.queue.yaml`

## Пропущены (done)

- `T-HUB-002`
- `T-HUB-003`
- `T-HUB-004`
- `T-HUB-005`
- `T-HUB-010`
- `T-HUB-011`
- `T-HUB-012`
- `T-HUB-013`
- `T-HUB-014`
- `T-HUB-015`
- `T-HUB-006`
- `T-HUB-007`

## Очередь

| # | ID | План | Hard deps |
|---|----|------|-----------|
| 1 | T-HUB-016 | [plan-T-HUB-016-dsh-cc-hooks-bridge.md](plan-T-HUB-016-dsh-cc-hooks-bridge.md) | — |
| 2 | T-HUB-008 | [plan-T-HUB-008-dsh-epic-gate-plugin.md](plan-T-HUB-008-dsh-epic-gate-plugin.md) | T-HUB-016 |
| 3 | T-HUB-009 | [plan-T-HUB-009-dsh-rollout-docs.md](plan-T-HUB-009-dsh-rollout-docs.md) | T-HUB-008, T-HUB-016 |
| 4 | T-HUB-017 | [plan-T-HUB-017-loop-observability-foundation.md](plan-T-HUB-017-loop-observability-foundation.md) | — |
| 5 | T-HUB-018 | [plan-T-HUB-018-loop-incident-autopilot.md](plan-T-HUB-018-loop-incident-autopilot.md) | T-HUB-017 |
| 6 | T-HUB-019 | [plan-T-HUB-019-dsh-board-sync-enrichments.md](plan-T-HUB-019-dsh-board-sync-enrichments.md) | — |
| 7 | T-HUB-020 | [plan-T-HUB-020-dsh-board-epic-loop.md](plan-T-HUB-020-dsh-board-epic-loop.md) | — |
| 8 | T-HUB-021 | [plan-T-HUB-021-pydantic-ai-output-cap.md](plan-T-HUB-021-pydantic-ai-output-cap.md) | — |
| 9 | T-HUB-022 | [plan-T-HUB-022-runtime-pydantic-schemas.md](plan-T-HUB-022-runtime-pydantic-schemas.md) | — |
| 10 | T-HUB-023 | [plan-T-HUB-023-hooks-llm-fallbacks.md](plan-T-HUB-023-hooks-llm-fallbacks.md) | T-HUB-021 |
| 11 | T-HUB-024 | [plan-T-HUB-024-validate-traceability.md](plan-T-HUB-024-validate-traceability.md) | — |
| 12 | T-HUB-025 | [plan-T-HUB-025-product-constitution-bootstrap.md](plan-T-HUB-025-product-constitution-bootstrap.md) | — |
| 13 | T-HUB-026 | [plan-T-HUB-026-spec-reconcile-workflow.md](plan-T-HUB-026-spec-reconcile-workflow.md) | — |

## Handoff

- Loop читает **только** `roadmap-epics.queue.yaml` (default path).
- После MULTI-EPIC PLAN → `BACK ROADMAP MERGE` → `BACK DECOMPOSE` первого id из queue.
