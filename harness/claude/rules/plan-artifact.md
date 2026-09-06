---
paths:
  - "memory-bank/**/plan-*.md"
  - "memory-bank/**/plan/decompose-*/**"
  - "memory-bank/**/plan/**"
  - "memory-bank/**/gap/gap-*.md"
  - "memory-bank/**/plan-*-GAP-*.md"
  - "memory-bank/back/plan/**"
  - "memory-bank/front/plan/**"
  - "memory-bank/integration/plan/**"
  - "memory-bank/**/security/plan/**"
  - "memory-bank/**/refactor/plan/**"
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
- **Coverage rubric:** covered row ⇒ measurable `verify` у sNN/eNN (runnable pytest/`rg`/CLI; stage = delta+files; NFR/AC− не map-only). Канон: `workflow-*-decompose.mdc` §Coverage rubric
- **Promote gate:** `validate-decompose-tree` + `validate-traceability` CRITICAL=0 + ANALYZE artifact/`ANALYZE deferred` до FINISH DECOMPOSE
- Предпочитать больше атомарных `sNN|eNN`, чем склейка; черновик count в plan — advisory
- Каждый shard: полный delta layer (`as_built` · `delta` · `deletes` · `out_of_scope`) + 2–4 checkpoints + tdd list; **без** полных тел кода
- **Replacement cleanup:** brownfield replace → непустой `deletes` у cutover-шага + `rg`/import-audit cp; greenfield → строка `n/a`; вечный shim без follow-up = FAIL
- **Spec-first replace:** technology axiom в plan; as-built = sunset inventory, не design template; pydantic/JSON → purge regex in-epic (@.cursor/rules/shared/workflow-spec-first-replace.mdc)
- FAIL: scaffolding-only очередь; requirement без sNN; этап канона «растворился» в layout/skeleton; replace без deletes; covered без measurable verify
- Канон процесса: `.cursor/rules/*_developer/workflow-decompose.mdc` §Maximal detail + §Replacement cleanup + §Coverage rubric

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

## Minimum bar (PLAN outcome prompt — `plan/<epic_id>/md/prompt.md`)

Канон: @.cursor/rules/shared/workflow-plan-outcome-prompt.mdc · шаблон @.cursor/templates/plan-prompt.md

- **REQUIRED** на каждый эпик вместе с `plan.md`. FINISH PLAN без файла / без `## Epic` → FAIL
- Две секции: `## Epic` (срез эпика) + `## Covering` (single = `n/a`; multi = один текст на всю нарезку)
- Абстрактный outcome, **не** HOW, **не** FR/AC ids, **не** transcript dump, **не** `roadmap/prompt-*.md`
- Файл начинается с `## Epic` (нет H1 `# Outcome prompt`, нет шапки Role/Deps/Source/ID). **FORBIDDEN** во всём файле: ID эпиков, пути чужих `plan/`. Читать соседние `plan/` из-за prompt — FAIL
- Prompt **не** раздувать до plan: Epic ~15–25 строк; telegraph-заглушка без границ → FAIL

## After Write

Run `wc -l` on the plan file. If under acceptance bar → expand before FINISH. Do not declare done.
Confirm `md/prompt.md` starts with `## Epic` (no `# Outcome prompt` / Role·Deps header), has `## Covering`, and contains no epic IDs / no `plan/<id>/` paths. Do not read sibling `plan/` to write Covering.
For architecture shards: verify mermaid blocks exist before FINISH.
For decompose: verify Requirements coverage + Stages coverage + Outcome map + Replacement cleanup exist and have no empty requirement / orphan-replace rows before FINISH.
