---
paths:
  - "memory-bank/**/plan-*.md"
  - "memory-bank/**/plan/decompose-*/**"
  - "memory-bank/**/gap/gap-*.md"
  - "memory-bank/**/plan-*-GAP-*.md"
  - "memory-bank/back/plan/plan-*.md"
  - "memory-bank/front/plan/plan-*.md"
  - "memory-bank/integration/plan/plan-*.md"
  - "memory-bank/**/security/plan/plan-*.md"
  - "memory-bank/**/refactor/plan/plan-*.md"
  - "memory-bank/architecture/**"
---

# PLAN / GAP / ARCHITECTURE / DECOMPOSE artifacts — NO OUTPUT ECONOMY

When creating or editing files matching these paths:

## Absolute rules

1. **Token economy / telegraph / «max 3 sentences» / 200-line caps DO NOT APPLY** to this file.
2. **Chat brevity does not limit** this file. Short reply to user ≠ short plan/map/decompose.
3. **Lean load ≠ lean write.** Context may stay focused; this artifact must be exhaustive.
4. Truncating «для экономии контекста / токенов» = **FAIL**. Rewrite longer.
5. **Multi-epic from research:** if PLAN input is research/audit with ≥2 cut criteria → **split** into N `plan-<epic_id>-*.md` + `roadmap-<slug>-epics.md` (@.cursor/rules/shared/workflow-plan-multi-epic.mdc). One mega-plan that omits detail instead of splitting = **FAIL**.

## Minimum bar (DECOMPOSE — `decompose-*/`)

- **Maximal detail:** все этапы плана/канона + все AC+/AC−/FR/NFR → покрытия в index (`## Requirements coverage`, `## Stages coverage`, `## Outcome map`, `## Replacement cleanup`)
- Предпочитать больше атомарных `sNN|eNN`, чем склейка; черновик count в plan — advisory
- Каждый shard: полный delta layer (`as_built` · `delta` · `deletes` · `out_of_scope`) + 2–4 checkpoints + tdd list; **без** полных тел кода
- **Replacement cleanup:** brownfield replace → непустой `deletes` у cutover-шага + `rg`/import-audit cp; greenfield → строка `n/a`; вечный shim без follow-up = FAIL
- FAIL: scaffolding-only очередь; requirement без sNN; этап канона «растворился» в layout/skeleton; replace без deletes
- Канон процесса: `.cursor/rules/*_developer/workflow-decompose.mdc` §Maximal detail + §Replacement cleanup

## Minimum bar (architecture — `memory-bank/architecture/**`)

- Brownfield VAN must produce real as-built content, not stubs-only
- Required mermaid: service interaction + data-flow; ERD or explicit `erd: n/a`
- Missing layer → explicit `absent` / `n/a`, never silent omit
- Session van log stays thin; detail lives in architecture shards

## Minimum bar (INTEG GAP — `gap-*.md`)

- **FAIL** if only parity matrix / ID table without executable work
- Required per every `G-BF*` / `G-FB*`: as-is asymmetry → what BACK/FRONT/INTEG must do → done checkboxes (шаблон `.cursor/templates/integration-gap.md` §«Работы по gap»)
- Medium detail OK (full AC/wire may live in `plan-*-GAP-*`); gap itself must still be actionable without re-reading implement bullets

## Minimum bar (INTEG portal plan)

If scope is portal/journey / file is `plan-INTEG-*`:

- **Hard FAIL** if artifact is TOC-only (registry table + short rollout without per-element detail)
- Prefer **≥400 lines** OR equivalent density: every UI element gets its own subsection (§UI, §API today, §Contract outline, §wire, §tests) — not one mega-table alone
- Every `frontend/src/app/**/page.tsx` route must appear
- Guides (`/guides`, `/guides/[slug]`) required
- API today must use ✅ / ⚠️ mock / ❌ missing honestly (not all ✅)
- Rollout must use **eNN** element steps, not layer s01-migration / s02-endpoint

## After Write

Run `wc -l` on the plan file. If under acceptance bar → expand before FINISH. Do not declare done.
For architecture shards: verify mermaid blocks exist before FINISH.
For decompose: verify Requirements coverage + Stages coverage + Outcome map + Replacement cleanup exist and have no empty requirement / orphan-replace rows before FINISH.
