# Filter key matrix — contract-first

**Rule:** write matrix in `memory-bank/integration/contracts/<domain>.md` **before** any filter-utils or mapping_filters code.

## Template

| UI field | List endpoint key | Param type | Stats endpoint key | Join path |
|----------|-------------------|------------|--------------------|-----------|
| city | `city__slug` | `filters` | `city_id` | City |
| difficulty | `difficulty` | `filters` | `difficulty` | flat |
| minPrice | `price__gte` | `gt` | `price__gte` | flat |
| maxPrice | `price__lte` | `lt` | `price__lte` | flat |
| dateRange | — | `period` | — | `created_at` |

## Real-world lesson: one UI → many API keys

Dashboard pattern (validated in production integration):

| UI field | Call API | Transcription API | Agent API |
|----------|----------|-------------------|-----------|
| country | `transcription__country_id` | `country_id` | `transcription__country_id` |
| scenario | `scenario_id` | `call__scenario_id` | `call__scenario_id` |
| agent | `agent_id` | `call__agent_id` | `call__agent_id` |

**Without matrix:** 6+ copy-pasted `buildXxxApiFilters` functions, drift, bugs.

**With matrix:** one builder per endpoint column, generated from contract table.

## Default filters column

| Endpoint | Default filters (merge) | Source |
|----------|-------------------------|--------|
| `/transcription/list` | `status: ["Assessment Completed"]` | business rule |
| `/call/score` | `transcription__status: ["Assessment Completed"]` | business rule |

Front: `mergeFilters(defaultFiltersFromContract, uiFilters)`.

## Contract §0.11 pairs

| Back file:symbol | Front file:symbol | Filter keys covered |
|------------------|-------------------|---------------------|
| `schema.py:IFilter` | `<domain>-filters.ts:buildListApiFilters` | flat keys |
| `schema.py:CityIFilter` | same builder | `city__*` |
| `endpoints/activity.py:mapping_filters.city` | builder join keys | path verified |

##  catalog example (proposal)

| UI (catalog) | API key | Param | Join |
|--------------|---------|-------|------|
| city | `city__slug` | filters | City |
| difficulty | `difficulty` | filters | flat |
| duration | `duration_type` | filters | flat |
| emotion | `emotion__slug` | filters | Emotion M2M |
| minPrice | `price__gte` | gt | flat |
| maxPrice | `price__lte` | lt | flat |

## When keys differ — checklist

- [ ] Contract table has **one row per endpoint variant**
- [ ] Separate `buildXxxApiFilters` per variant (not one mega-function)
- [ ] vitest asserts correct key per endpoint
- [ ] §0.11 grep: each key in front builder ↔ IFilter / RelationIFilter
