---
description: integ PLAN — exhaustive portal wire plan (NO output economy)
---

# INTEG PLAN — Claude Code

`SUSPENSION GUARD active — plan output unlimited`

Do **not** apply token-economy telegraph, 200-line limits, or chat-brief style to the plan file.

If `$ARGUMENTS` / attachments are research/audit with ≥2 wire axes → `.cursor/rules/shared/workflow-plan-multi-epic.mdc`: roadmap + **N** full plans (each portal-scope plan still ≥400 lines). Do **not** glue into one mega-plan.

## Before any Write

1. Read and follow: `.claude/skills/role-command/SKILL.md` for **INTEG PLAN**
2. Read: `.cursor/rules/integration_developer/workflow-plan.mdc`
3. Read: `.cursor/rules/integration_developer/isolation_rules/_lean/plan.mdc`
3b. Research multi-axis → `.cursor/rules/shared/workflow-plan-multi-epic.mdc`
4. Read: `.claude/rules/plan-artifact.md`
5. Inventory with tools (mandatory, not from memory):
   - Glob `frontend/src/app/**/page.tsx`
   - List components under `frontend/src/components/{home,catalog,activity,dashboard,provider,guides,auth}`
   - Grep mock fallbacks in `frontend/src/lib/*-api.ts` and pages
   - List `memory-bank/back/implement/*.md` + `memory-bank/front/implement/*.md` (portal-relevant only)
6. Announce in chat: lists of routes found + `SUSPENSION GUARD active`

## Write target

`memory-bank/integration/plan/plan-<task_id>.md` (default slug `INTEG-JOURNEY-YYYYMMDD` if unspecified)

Multi-epic research: also `roadmap-<slug>-epics.md` + one plan file per epic (template roadmap: `.cursor/templates/roadmap-epics.md`).

Template structure: `.cursor/templates/integration-plan.md` — **expand far beyond template**. Template is skeleton only.

## Required content (exhaustive)

1. **Scope:** portal
2. **Element registry** table (all routes × elements)
3. **Per-element sections** for every P0/P1 element at minimum:
   - §UI (route, real component path)
   - §Data need
   - §API today (✅ / ⚠️ mock / ❌) + real endpoint path as-built
   - §Contract outline (request/response keys)
   - §BACK / §FRONT deliverables for wire
   - §Verify (§0.11 pair + test hint)
4. **API inventory** full table
5. **User journeys** J1… with elements
6. **Rollout** as **e01, e02, …** (element-first). Forbidden: layer slice `s01 migration → s02 endpoint → s03 api.ts`
7. **Test matrix** + **Risks** + **Handoff**
8. Include **guides**, auth/cabinet button path, home Hero/CityGrid/Showcase, checkout, dashboard, provider CRM

## Acceptance — BEFORE FINISH (run in shell)

```bash
wc -l memory-bank/integration/plan/plan-*.md | sort -n | tail -5
```

**FAIL and expand** if:

- Main plan file **< 400 lines**, OR
- Missing `/guides` in registry, OR
- Rollout uses layer-first sNN instead of eNN, OR
- Only registry table without per-element § sections for P0 items

Chat summary to user: short OK. Plan file: long.

$ARGUMENTS
