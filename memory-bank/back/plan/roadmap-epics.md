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
- `memory-bank/back/plan/roadmap-dsh-mb-board-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-dsh-loop-backend-epics.queue.yaml`

## Пропущены (done)

- `T-HUB-011`
- `T-HUB-006`
- `T-HUB-002`
- `T-HUB-003`
- `T-HUB-004`
- `T-HUB-010`

## Очередь

| # | ID | План | Hard deps |
|---|----|------|-----------|
| 1 | T-HUB-012 | [plan-T-HUB-012-audit-converge.md](plan-T-HUB-012-audit-converge.md) | — |
| 2 | T-HUB-013 | [plan-T-HUB-013-idea-decide-constitution.md](plan-T-HUB-013-idea-decide-constitution.md) | — |
| 3 | T-HUB-005 | [plan-T-HUB-005-simplify-docs.md](plan-T-HUB-005-simplify-docs.md) | — |
| 4 | T-HUB-007 | [plan-T-HUB-007-dsh-profiles-presets.md](plan-T-HUB-007-dsh-profiles-presets.md) | — |
| 5 | T-HUB-014 | [plan-T-HUB-014-dsh-mb-board-sync.md](plan-T-HUB-014-dsh-mb-board-sync.md) | — |
| 6 | T-HUB-015 | [plan-T-HUB-015-dsh-board-arm-loop.md](plan-T-HUB-015-dsh-board-arm-loop.md) | T-HUB-014 |
| 7 | T-HUB-016 | [plan-T-HUB-016-dsh-cc-hooks-bridge.md](plan-T-HUB-016-dsh-cc-hooks-bridge.md) | T-HUB-007 |
| 8 | T-HUB-008 | [plan-T-HUB-008-dsh-epic-gate-plugin.md](plan-T-HUB-008-dsh-epic-gate-plugin.md) | T-HUB-007, T-HUB-016 |
| 9 | T-HUB-009 | [plan-T-HUB-009-dsh-rollout-docs.md](plan-T-HUB-009-dsh-rollout-docs.md) | T-HUB-007, T-HUB-008, T-HUB-016 |

## Handoff

- Loop читает **только** `roadmap-epics.queue.yaml` (default path).
- После MULTI-EPIC PLAN → `BACK ROADMAP MERGE` → `BACK DECOMPOSE` первого id из queue.
