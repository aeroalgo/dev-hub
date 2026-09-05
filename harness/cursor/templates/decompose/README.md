# Decompose templates

**Shard (BACK / FRONT / INTEG):** [epic-step.yaml](epic-step.yaml) — **единственный** канон: `schema: epic-decompose/v1`, `role: back|front|integ`, `as_built`/`delta` = list.

**FORBIDDEN:** invented schemas (`epic-decompose-shard/*`, `epic-decompose-step/*`, …), `as_built: {as_is, delta}` dict. DECOMPOSE FINISH: `epic_resolve.py validate-decompose-tree` (stop-gate fail-closed).

| Артефакт | Путь (layout v2) |
|----------|------|
| Human hub | `plan/<plan_id>/md/decompose-index.md` — шаблон [index.md](index.md) |
| Machine hub | `plan/<plan_id>/yaml/decompose-index.yaml` — канон status (`sync-index-yaml` / `mark-index-status`) |
| Shard | `plan/<plan_id>/yaml/steps/sNN\|eNN-<slug>.yaml` |
| Purge shard (brownfield) | [legacy-purge-step.yaml](legacy-purge-step.yaml) — `sunset_inventory` + `grep_control` + cp-inventory-a/b/c/i |

**`<plan_id>` HARD:** = stem plan-файла без `plan-`, **включая descriptive slug** (`T-HUB-033-harness-execution-discipline`, не `T-HUB-033`). Queue short `id:` ≠ имя папки. Канон: `shared/epic-scoped-paths.mdc` §Folder naming. Parallel: `implement/<plan_id>/`.

**FORBIDDEN:** `decompose-<plan_id>/` · писать `yaml/index.md` или `yaml/index.yaml` · дубль `index.md` + `decompose-index.md`.

**Status:** только `mark-index-status` / `finalize-step` (пишет yaml + зеркалит md). После правки таблицы md → `sync-index-yaml`.  
**IMPLEMENT load_now:** work shard + `yaml/decompose-index.yaml` (не human `decompose-index.md`, не `implement/index.md`).

**Delta layer (все роли):** `as_built` · `delta` · `deletes` · `out_of_scope` — что уже есть / что меняем / что **удаляем** / что не трогать.  
**Replacement cleanup:** brownfield replace → index `## Replacement cleanup` (Kind A|B|C|I + Fallback?) + ladder add→wire→enforce→purge + `deletes:` + финальный `*-legacy-fallback-purge` с **полным inventory scan** (`legacy-purge-step.yaml`: `sunset_inventory`, `grep_control`, cp-inventory-a/b/c/**i**). AUDIT: `sunset_inventory_scan` + `sot_enforce_scan`. Канон: `shared/workflow-legacy-fallback-cleanup.mdc` §2 · `shared/workflow-behavior-first.mdc` §3.  
**Checkpoints:** 2–4 атомарных cp; у каждого `criterion` + `verify` (не один mega-cp = весь goal).  
**Granularity:** один IMPLEMENT = один prod-модуль или один test-file; атомарность внутри — checkpoints, не лишние sNN.  
**Maximal detail:** в `md/decompose-index.md` обязательны `## Requirements coverage` + `## Stages coverage` + `## Outcome map` (+ `## Replacement cleanup`) — DECOMPOSE-артефакт, не грузить в IMPLEMENT.

**needs_creative (BACK/FRONT):** `no` | `yes (CR-…)` | `yes (CR-…) — **closed**` · index колонка `yes (CR-…) ✅` после close.
