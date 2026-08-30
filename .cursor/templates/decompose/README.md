# Decompose templates

**Shard (BACK / FRONT / INTEG):** [epic-step.yaml](epic-step.yaml) — **единственный** канон: `schema: epic-decompose/v1`, `role: back|front|integ`, `as_built`/`delta` = list.

**FORBIDDEN:** invented schemas (`epic-decompose-shard/*`, `epic-decompose-step/*`, …), `as_built: {as_is, delta}` dict. DECOMPOSE FINISH: `epic_resolve.py validate-decompose-tree` (stop-gate fail-closed).

| Артефакт | Путь |
|----------|------|
| Human hub | `decompose-<plan_id>/index.md` — [index.md](index.md) |
| Machine hub | `decompose-<plan_id>/index.yaml` — канон status (`sync-index-yaml` / `mark-index-status`) |
| Shard | `decompose-<plan_id>/sNN\|eNN-<slug>.yaml` |

**Status:** только `mark-index-status` / `finalize-step` (пишет yaml + зеркалит md). После правки таблицы md → `sync-index-yaml`.  
**IMPLEMENT load_now:** work shard + `index.yaml` (не этот `index.md`, не `implement/index.md`).

**Delta layer (все роли):** `as_built` · `delta` · `deletes` · `out_of_scope` — что уже есть / что меняем / что **удаляем** / что не трогать.  
**Replacement cleanup:** brownfield replace → index `## Replacement cleanup` (Kind A|B|C + Fallback?) + `deletes:` + финальный `*-legacy-fallback-purge` + `rg`/entrypoint inventory. Канон: `shared/workflow-legacy-fallback-cleanup.mdc`.  
**Checkpoints:** 2–4 атомарных cp; у каждого `criterion` + `verify` (не один mega-cp = весь goal).  
**Granularity:** один IMPLEMENT = один prod-модуль или один test-file; атомарность внутри — checkpoints, не лишние sNN.  
**Maximal detail:** в `index.md` обязательны `## Requirements coverage` + `## Stages coverage` + `## Outcome map` (+ `## Replacement cleanup`) — DECOMPOSE-артефакт, не грузить в IMPLEMENT.

**needs_creative (BACK/FRONT):** `no` | `yes (CR-…)` | `yes (CR-…) — **closed**` · index колонка `yes (CR-…) ✅` после close.
