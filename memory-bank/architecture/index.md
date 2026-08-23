# Architecture map — index (dev-hub)

**Last refresh:** 2026-08-22  
**Refreshed by:** BACK IMPLEMENT T-HUB-003 s05 (workers + orphan gaps)  
**Mode:** brownfield  
**Repo:** dev-hub (tooling hub: rules, hooks, loop)  
**graphify:** attempt N/A — в корне нет `.venv` / `.venv/bin/graphify` / `graphify-out/graph.json`. Inventory: Read README, `bin/*`, `loop/*`, `.claude/hooks|agents|project.env`, `make/product.mk`. Nested graphify-out не создавался.  
**Scope rule:** только этот репозиторий; product trees и follow workspace paths — вне VAN.

## Shards

| Shard | Path | Status |
|-------|------|--------|
| Overview | [overview.md](overview.md) | current |
| Services | [services.md](services.md) | current |
| Data flow | [data-flow.md](data-flow.md) | current |
| ERD | [erd.md](erd.md) | n/a (нет доменной БД) + file runtime map |
| Workers | [workers.md](workers.md) | current (loop sessions; нет queue broker) |
| Containers | [containers.md](containers.md) | n/a (нет compose/Dockerfile в хабе) |
| Frontend | [frontend.md](frontend.md) | absent |

## Mermaid checklist

- [x] service interaction — `services.md`
- [x] data-flow — `data-flow.md`
- [x] ERD or explicit n/a — `erd.md`

## Gaps / unknowns

1. В хабе нет `.venv` / `pyproject.toml` — как канонически гонять `loop/tests` из корня хаба не зафиксировано в коде (README loop ссылается на `.venv/bin/pytest`).
2. `projects/` пуст — per-product env overrides не используются.
3. Содержимое `runtime/<slug>/` отражает **прикреплённые** продукты; VAN хаба описывает только схему runtime, не epics продуктов.

## Related

- [projectbrief.md](../projectbrief.md)
- [techContext.md](../techContext.md)
- [systemPatterns.md](../systemPatterns.md)
- Session: [back/van/van-20260816.md](../back/van/van-20260816.md)
