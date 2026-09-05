# Query params — routing table

Mirror **exactly** on front in `lib/filters/<domain>-filters.ts`.

## Param types

| Param | Value type | Use for | Example |
|-------|------------|---------|---------|
| `filters` | JSON `dict[str, list[str]]` | enum, multiselect, `relation__column` | `{"difficulty":["beginner"],"city__slug":["sochi"]}` |
| `gt` / `lt` / `eq` | JSON `dict[str, number]` | numeric bounds | `gt={"price__gte":5000}` |
| `period` | quoted `"YYYY-MM-DD:YYYY-MM-DD"` | date range | `"2025-01-01:2025-12-31"` |
| `search` | string | full-text | `search=rafting` |
| `ascending` / `descending` | column key | sort | `descending=created_at` |
| `page`, `size` | int | pagination | `page=1&size=20` |
| `records` | `all` | include soft-deleted | rare |

## Rules

1. **Numbers → `gt`/`lt`/`eq`**, never inside `filters` JSON
2. **Multiselect → `filters`** with string array values
3. **Join → `relation__column`** key in `filters` JSON
4. **`period` in URL** — value often wrapped in quotes (validator strips them)
5. **Default filters** — merge on BACK only for business rules; front uses `mergeFilters(existing, new)`

## period formatting (front)

```typescript
export function formatPeriod(dateFrom: Date, dateTo: Date): string {
  const fmt = (d: Date) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, "0")
    const day = String(d.getDate()).padStart(2, "0")
    return `${y}-${m}-${day}`
  }
  return `"${fmt(dateFrom)}:${fmt(dateTo)}"`
}
```

Use local start/end of day to avoid timezone drift.

## buildQueryParams pattern

```typescript
export function buildQueryParams(state: CatalogFilterState): Record<string, string> {
  const params: Record<string, string> = {}
  const filters = buildCatalogApiFilters(state)
  if (Object.keys(filters).length) params.filters = JSON.stringify(filters)
  if (state.minPrice != null) params.gt = JSON.stringify({ "price__gte": state.minPrice })
  if (state.maxPrice != null) params.lt = JSON.stringify({ "price__lte": state.maxPrice })
  if (state.dateFrom && state.dateTo) params.period = formatPeriod(state.dateFrom, state.dateTo)
  return params
}
```

## URL assembly

```typescript
export function buildApiUrl(baseUrl: string, queryParams: Record<string, string>): string {
  const url = new URL(baseUrl)
  for (const [k, v] of Object.entries(queryParams)) {
    if (v != null) url.searchParams.set(k, v)
  }
  return url.toString()
}
```

**Forbidden:** building `filters` JSON inline in React components — only via `lib/filters/`.
