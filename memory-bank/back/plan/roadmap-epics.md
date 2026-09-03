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
- `memory-bank/back/plan/roadmap-back-plan-gstack-adapt-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-pydantic-reliability-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-phase-verify-agents-runtime-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-dsh-loop-backend-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-spec-maturity-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-harness-maturity-borrowings-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-workflow-pack-framework-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-suite-hygiene-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-sunset-inventory-agent-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-loop-session-contract-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-harness-universal-runtime-epics.queue.yaml`

## Пропущены (done)

- `T-HUB-057`
- `T-HUB-058`
- `T-HUB-053`
- `T-HUB-046`
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
- `T-HUB-029`
- `T-HUB-027`
- `T-HUB-023`
- `T-HUB-039`
- `T-HUB-006`
- `T-HUB-007`
- `T-HUB-016`
- `T-HUB-008`
- `T-HUB-009`
- `T-HUB-024`
- `T-HUB-025`
- `T-HUB-026`
- `T-HUB-030`
- `T-HUB-031`
- `T-HUB-032`
- `T-HUB-033`
- `T-HUB-034`
- `T-HUB-035`
- `T-HUB-036`
- `T-HUB-037`
- `T-HUB-038`
- `T-HUB-040`
- `T-HUB-045`
- `T-HUB-054`
- `T-HUB-055`
- `T-HUB-056`
- `T-HUB-041`
- `T-HUB-042`
- `T-HUB-043`
- `T-HUB-044`

## Очередь

| # | ID | План | Hard deps |
|---|----|------|-----------|
| 1 | T-HUB-047 | [plan-T-HUB-047-harness-mb-scaffold-epic-layout.md](plan-T-HUB-047-harness-mb-scaffold-epic-layout.md) | — |
| 2 | T-HUB-048 | [plan-T-HUB-048-workflow-pack-registry.md](plan-T-HUB-048-workflow-pack-registry.md) | — |
| 3 | T-HUB-049 | [plan-T-HUB-049-workflow-pack-phase-router.md](plan-T-HUB-049-workflow-pack-phase-router.md) | T-HUB-048 |
| 4 | T-HUB-050 | [plan-T-HUB-050-workflow-pack-memory-bank-paths.md](plan-T-HUB-050-workflow-pack-memory-bank-paths.md) | T-HUB-048 |
| 5 | T-HUB-051 | [plan-T-HUB-051-workflow-pack-reference-video.md](plan-T-HUB-051-workflow-pack-reference-video.md) | T-HUB-049, T-HUB-050 |
| 6 | T-HUB-052 | [plan-T-HUB-052-workflow-pack-adoption-docs.md](plan-T-HUB-052-workflow-pack-adoption-docs.md) | T-HUB-051 |
| 7 | T-HUB-059 | [plan-T-HUB-059-harness-claude-agents-sot-complete.md](plan-T-HUB-059-harness-claude-agents-sot-complete.md) | — |

## Handoff

- Loop читает **только** `roadmap-epics.queue.yaml` (default path).
- `BACK PLAN` **сам** вызывает `roadmap-merge` в той же сессии (не отдельный next `BACK ROADMAP MERGE`).
- Next: `BACK DECOMPOSE` первого id из queue.
- Ручной `BACK ROADMAP MERGE` — только если канон устарел без PLAN.
