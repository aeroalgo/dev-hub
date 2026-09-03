# Anti-patterns — do not repeat

## BACK

| Anti-pattern | Why bad | Do instead |
|--------------|---------|------------|
| Raw SQL / manual `where()` in list endpoint | bypasses validation, drift | QueryBuilder + mapping_filters |
| Numeric range in `filters` JSON | wrong param type, QB mismatch | `gt`/`lt`/`eq` |
| Missing `mapping_filters` for `__` key | 422 or silent wrong join | add path + RelationIFilter |
| `IFilter` field without contract entry | undocumented key | update contract first |

## FRONT

| Anti-pattern | Why bad | Do instead |
|--------------|---------|------------|
| 6 copy-pasted `buildXxxApiFilters` without matrix | drift, untestable | contract table + one builder per endpoint |
| `console.log` in filter-utils | noise, prod leak | remove; vitest for debug |
| Building filters JSON in JSX/components | untestable, duplicate | `lib/filters/<domain>-filters.ts` |
| Mock data in prod fetch path | hides contract bugs | typed error + offline dev flag only |
| Same query key for all endpoints | stale wrong cache | include endpoint + serialized filters |
| One builder for Call + Transcription APIs | wrong keys on one API | per-endpoint builders from matrix |

## INTEG process

| Anti-pattern | Why bad | Do instead |
|--------------|---------|------------|
| UI before contract | wrong keys baked in | INTEG PLAN → contract → implement |
| Opening external reference repo | token cost, path confusion | this skill lazy refs |
| Plan shard as source of truth | intent ≠ fact | `back/implement/` + `front/implement/` |
| Skip §0.11 grep | orphan endpoints | INTEG QA checklist |

## fec-web-acc technical debt (explicitly rejected)

- Monolithic 566-line `filter-utils.ts` with debug logs
- Duplicate `buildCallApiFilters` / `buildCallApiFiltersForDashboard` / history variants without shared matrix
- Fallback to mock on any API error in dashboard hooks

## -specific

| Skip from reference | Reason |
|---------------------|--------|
| `user_scope` in QueryBuilder | optional; verify `core/base/query_builder.py` |
| Partner filter mixin | not in  monolith scope |
| Raw SQL pagination for agent stats | exception only; document in contract |
