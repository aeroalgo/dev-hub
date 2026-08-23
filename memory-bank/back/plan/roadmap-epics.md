# Roadmap: active epics (merged canon)

**Роль:** BACK  
**Назначение:** единая очередь для loop (`EPIC_CHAIN_ROADMAP` / `roadmap-advance`).  
**Machine queue:** [`roadmap-epics.queue.yaml`](roadmap-epics.queue.yaml)  
**Команда:** `BACK ROADMAP MERGE`  
**Порядок (2026-08-23):** SpecKit boost **сначала** → leftover workflow-loop (005) → **DSH в хвосте** (ручная перестановка после CLI merge по запросу).

Slug-roadmap (`roadmap-<slug>-epics.*`) — источники; этот файл — канон.

---

## Источники

- `memory-bank/back/plan/roadmap-speckit-workflow-boost-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-workflow-loop-hardening-epics.queue.yaml`
- `memory-bank/back/plan/roadmap-dsh-loop-backend-epics.queue.yaml`

## Пропущены (done)

- `T-HUB-002`
- `T-HUB-003`
- `T-HUB-004`

## Очередь

| # | ID | План | Hard deps | Блок |
|---|----|------|-----------|------|
| 1 | T-HUB-010 | [plan-T-HUB-010-clarify-spec-quality.md](plan-T-HUB-010-clarify-spec-quality.md) | — | SpecKit |
| 2 | T-HUB-011 | [plan-T-HUB-011-analyze-pre-implement.md](plan-T-HUB-011-analyze-pre-implement.md) | T-HUB-010 | SpecKit |
| 3 | T-HUB-012 | [plan-T-HUB-012-audit-converge.md](plan-T-HUB-012-audit-converge.md) | T-HUB-010 | SpecKit |
| 4 | T-HUB-013 | [plan-T-HUB-013-idea-decide-constitution.md](plan-T-HUB-013-idea-decide-constitution.md) | — | SpecKit |
| 5 | T-HUB-005 | [plan-T-HUB-005-simplify-docs.md](plan-T-HUB-005-simplify-docs.md) | — | workflow-loop leftover |
| 6 | T-HUB-006 | [plan-T-HUB-006-dsh-loop-runtime-adapter.md](plan-T-HUB-006-dsh-loop-runtime-adapter.md) | — | DSH |
| 7 | T-HUB-007 | [plan-T-HUB-007-dsh-profiles-presets.md](plan-T-HUB-007-dsh-profiles-presets.md) | T-HUB-006 | DSH |
| 8 | T-HUB-008 | [plan-T-HUB-008-dsh-epic-gate-plugin.md](plan-T-HUB-008-dsh-epic-gate-plugin.md) | T-HUB-006, T-HUB-007 | DSH |
| 9 | T-HUB-009 | [plan-T-HUB-009-dsh-rollout-docs.md](plan-T-HUB-009-dsh-rollout-docs.md) | T-HUB-006, T-HUB-007, T-HUB-008 | DSH |

## Handoff

- Loop читает **только** `roadmap-epics.queue.yaml` (default path).
- Next: `BACK DECOMPOSE` **T-HUB-010**.
