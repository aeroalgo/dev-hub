# Contract: <domain-slug>
**Task ID:** <T-xxx>
**Status:** draft | active | done

## Entity
- **Model:** `app.<entity>.model.<Entity>`
- **Table:** `<table_name>`
- **Scope:** partner / public

## Endpoints
| Method | Path | Purpose | Default filters |
|--------|------|---------|-----------------|
| GET | `/api/v1/<resource>/list` | list + pagination | `{}` |

## UI FilterState
```typescript
interface <Domain>FilterState {
  // UI fields
}
```

## Filter key matrix
| UI field | List endpoint key | Param type | Facets endpoint | mapping_filters path |
|----------|-------------------|------------|-----------------|----------------------|
| | | `filters` \| `gt` \| `lt` \| `period` | | |

## QueryBuilder config
- **model:** `<Entity>`
- **period_mode:** `created_at`
- **mapping_filters:** @.agents/skills/query-builder/references/JOINS-AND-MAPPING.md
- **query params:** @.agents/skills/query-builder/references/QUERY-PARAMS.md

## Query params (PaginateQueryParams)
- `filters`: JSON dict, values = string[] — enum, multiselect, `relation__column`
- `gt` / `lt` / `eq`: JSON dict — числовые границы (`price__gte`, `price__lte`)
- `period`: `"YYYY-MM-DD:YYYY-MM-DD"` on `<period_field>`
- `page`, `size`, `search`, `ascending`, `descending`

## Response
- `data.items[]`, `data.total`, `data.page`, `data.size`, `data.pages`
- `meta.read_table_mapping[]` — if table UI

## BACK files
- `app/<entity>/schema.py`
- `api/v1/endpoints/<entity>.py`
- `tests/api/test_<entity>.py`

## FRONT files
- `frontend/src/lib/api/<domain>.ts`
- `frontend/src/lib/filters/<domain>-filters.ts`
- `frontend/src/lib/query-keys/<domain>.ts`
- `frontend/src/hooks/use-<domain>.ts`

## Consumers
- `frontend/src/app/...`
- `frontend/src/components/...`

## §0.11 pairs
| Back | Front | BACK implement ref | FRONT implement ref |
|------|-------|--------------------|---------------------|
| | | | |

> Пары только из implement §Файлы + grep verify. Plan/decompose shards — не источник.

## Production rollout contract

- **Source of truth:** `activeContext.md` + decompose index + implement artifact; `state.json` is status/checkpoint telemetry and never the durable cursor.
- **Scheduler:** `loop-dag/v2` validates `depends_on` and runs dependency-ready nodes sequentially in one checkout; no implicit parallel or distributed-lock guarantee.
- **Compatibility:** v1 input is accepted only through an explicit compatibility diagnostic/adapter; malformed or ambiguous metadata fails closed.
- **Phases:** A observe → B shadow → C canary → D expand → E enforce.
- **Recovery / rollback:** preserve event evidence, validate `resume_from_step` and checkpoint/index agreement, then restore the last validated cursor. Manual fallback must be labelled and must not reset to first pending. T-034 policy remains an explicit boundary.
