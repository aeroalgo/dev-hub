# Tasks — index (dev-hub)

## Active

| ID | Title | Level | Step | Status | Progress |
|----|-------|-------|------|--------|----------|
| T-HUB-010 | SpecKit adapt — CLARIFY + spec quality | L3 | PLAN done | active | [plan](back/plan/plan-T-HUB-010-clarify-spec-quality.md) · canon #1 · next DECOMPOSE |
| T-HUB-011 | SpecKit adapt — ANALYZE pre-implement | L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-011-analyze-pre-implement.md) · deps T-HUB-010 |
| T-HUB-012 | SpecKit adapt — AUDIT converge | L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-012-audit-converge.md) · deps T-HUB-010 |
| T-HUB-013 | SpecKit adapt — IDEA decide + constitution | L2–L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-013-idea-decide-constitution.md) |
| T-HUB-005 | Simplify docs — cheatsheets/DX | L2–L3 | QA pass | queued | [qa](back/qa/T-HUB-005-simplify-docs/qa-20260822-simplify-docs.yaml) · next REFLECT · after SpecKit |
| T-HUB-006 | DSH loop runtime adapter | L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-006-dsh-loop-runtime-adapter.md) · DSH tail |
| T-HUB-007 | DSH profiles + presets | L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-007-dsh-profiles-presets.md) · deps T-HUB-006 |
| T-HUB-008 | DSH epic-gate plugin | L4 | PLAN done | queued | [plan](back/plan/plan-T-HUB-008-dsh-epic-gate-plugin.md) · deps T-HUB-006, T-HUB-007 |
| T-HUB-009 | DSH rollout docs + pilot | L2–L3 | PLAN done | queued | [plan](back/plan/plan-T-HUB-009-dsh-rollout-docs.md) · deps T-HUB-006…008 |
| T-HUB-002 | Canon sync — CLAUDE/role-command/archive/graphify | L3 | skipped done (merge) | EPIC_DONE* | merge skipped · verify if true DONE |
| T-HUB-003 | Loop halt + runtime root | L3 | REFLECT done | EPIC_DONE | [reflection](back/reflection/reflection-T-HUB-003-loop-halt.md) |
| T-HUB-004 | Hooks hygiene — verdict/NEED_HUMAN/dead re-exports | L3 | REFLECT done | EPIC_DONE | [reflection](back/reflection/reflection-T-HUB-004-hooks-hygiene.md) |

## Roadmap

| Artifact | Path |
|----------|------|
| **Canon (loop)** | [roadmap-epics.md](back/plan/roadmap-epics.md) · [roadmap-epics.queue.yaml](back/plan/roadmap-epics.queue.yaml) |
| Slug: workflow-loop | [roadmap-workflow-loop-hardening-epics.md](back/plan/roadmap-workflow-loop-hardening-epics.md) · [queue](back/plan/roadmap-workflow-loop-hardening-epics.queue.yaml) |
| Slug: dsh-loop-backend | [roadmap-dsh-loop-backend-epics.md](back/plan/roadmap-dsh-loop-backend-epics.md) · [queue](back/plan/roadmap-dsh-loop-backend-epics.queue.yaml) |
| Slug: speckit-workflow-boost | [roadmap-speckit-workflow-boost-epics.md](back/plan/roadmap-speckit-workflow-boost-epics.md) · [queue](back/plan/roadmap-speckit-workflow-boost-epics.queue.yaml) |
| Research | [audit/workflow-loop-20260816](audit/workflow-loop-20260816/index.md) · spec-kit/ (local) + chat analysis 2026-08-23 |

## Done (recent)

| ID | Title | Level | Step | Status | Progress |
|----|-------|-------|------|--------|----------|
| T-HUB-001 | Brownfield BACK VAN — as-built map хаба | L3 | VAN 2026-08-16 | done | [architecture/](architecture/index.md) · [van-20260816](back/van/van-20260816.md) |

## Progress

- T-HUB-001: architecture shards для tooling hub
- T-HUB-002…005: MULTI-EPIC PLAN из audit workflow-loop
- T-HUB-006…009: MULTI-EPIC PLAN DSH loop backend (opt-in runtime)
- T-HUB-010…013: MULTI-EPIC PLAN SpecKit workflow boost (clarify/analyze/audit-converge/idea-decide)

## Последние события

| Date | ID | Event |
|------|-----|-------|
| 2026-08-23 | canon | BACK ROADMAP MERGE · SpecKit first · DSH tail · next DECOMPOSE T-HUB-010 |
| 2026-08-23 | T-HUB-010…013 | BACK PLAN multi-epic speckit-workflow-boost · next ROADMAP MERGE |
| 2026-08-22 | T-HUB-004 | BACK REFLECT → EPIC_DONE · [reflection-T-HUB-004-hooks-hygiene](back/reflection/reflection-T-HUB-004-hooks-hygiene.md) |
| 2026-08-22 | T-HUB-004 | BACK QA PASS · [qa-20260822-hooks-hygiene](back/qa/T-HUB-004-hooks-hygiene/qa-20260822-hooks-hygiene.yaml) → next REFLECT |
| 2026-08-22 | T-HUB-003 | BACK REFLECT → EPIC_DONE · [reflection-T-HUB-003-loop-halt](back/reflection/reflection-T-HUB-003-loop-halt.md) |
| 2026-08-22 | T-HUB-002…009 | BACK ROADMAP MERGE → canon queue (8 epics) |
| 2026-08-22 | T-HUB-006…009 | BACK PLAN multi-epic dsh-loop-backend |
| 2026-08-16 | T-HUB-002…005 | BACK PLAN multi-epic workflow-loop-hardening |
| 2026-08-16 | T-HUB-001 | BACK VAN brownfield map (hub-only scope) |

## Complexity reference

| L | Scope |
|---|-------|
| L1 | 1–2 файла |
| L2 | 3–5 файлов |
| L3 | фича / многокомпонентная карта хаба |
| L4 | платформенная перестройка workflow |
