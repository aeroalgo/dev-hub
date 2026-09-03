# Integration timeline (canonical patterns)

Patterns below were validated in a reference project and ported to . **Do not consult external repos** — implement from this skill.

## Phase 1 — Backend QueryBuilder

- Extract `QueryBuilder.build()` as step pipeline (init → soft_delete → joins → filters → period → sort)
- `PaginateQueryParams` validators parse query string into row dicts
- `mapping_filters` with `path` tuples for join chains
- `IFilter` / relation `XxxIFilter` — invalid key → HTTP 422

## Phase 2 — Async DB

- Async session; query string contract unchanged

## Phase 3 — TanStack Query (front)

- Replace manual polling with `useQuery`
- Central `query-client.ts` + `QueryProvider`
- Query keys include serialized filters + period

## Phase 4 — Test infrastructure

- BACK: pytest on `?filters=`, `?period=`, 422 invalid key
- FRONT: vitest on filter-utils → URL; MSW for hooks optional

## Phase 5 — Dashboard filters E2E

- `filter-utils.ts`: per-endpoint builders (same UI → different API keys)
- Context: **tempFilters** (UI) vs **applied filters** (API) + Apply button
- Parallel fetch: each hook/API uses its own filter builder
- E2E: Apply → network requests contain `filters=` in URL

## Phase 6 — Extensions

- Extra query params (e.g. `scored_only`) — document in contract, mirror in `buildApiUrl`
- Reporting cache / invalidate on filter change

##  differences

| Reference extra |  |
|-----------------|-------------|
| `user_scope` / partner filter in QB | optional — check `core/base/query_builder.py` |
| Raw SQL pagination for stats | use only when QB cannot express query; document exception |
| Single `lib/filter-utils.ts` monolith | per-domain `frontend/src/lib/filters/<domain>-filters.ts` |

## When QueryBuilder does NOT apply

Portal-scoped endpoints (`/provider/slots`, moderate booking) — service layer + Pydantic, no `mapping_filters` list pipeline.
