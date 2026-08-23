# FRONT filter-utils mirror

## Layer separation (do not mix)

| File | Responsibility |
|------|----------------|
| `frontend/src/lib/filters/<domain>-filters.ts` | UI FilterState → API query params |
| `frontend/src/lib/api/<domain>.ts` | fetch + TypeScript types from contract |
| `frontend/src/lib/query-keys/<domain>.ts` | TanStack cache keys |
| `frontend/src/hooks/use-<domain>.ts` | orchestration |
| `contexts/<domain>-context.tsx` | shared state only if N consumers |

## Required functions

| Function | Purpose |
|----------|---------|
| `formatPeriod(dateFrom, dateTo)` | quoted period string |
| `buildXxxApiFilters(uiState)` | UI → filters dict **per endpoint** |
| `mergeFilters(existing, new)` | default endpoint filters + UI |
| `buildQueryParams(state, existing?)` | `{ filters?, period?, gt?, lt? }` |
| `buildApiUrl(baseUrl, params)` | URL with searchParams |

## Per-endpoint builders

If endpoints use different keys for same UI field — **separate builder each**:

```typescript
export function buildListApiFilters(state: CatalogFilterState): Record<string, string[]> {
  const f: Record<string, string[]> = {}
  if (state.city) f["city__slug"] = [state.city]
  if (state.difficulty) f["difficulty"] = [state.difficulty]
  return f
}

export function buildStatsApiFilters(state: CatalogFilterState): Record<string, string[]> {
  const f: Record<string, string[]> = {}
  if (state.city) f["city_id"] = [state.city]
  return f
}
```

Document mapping in contract **before** implementing builders.

## mergeFilters

```typescript
export function mergeFilters(
  existing: Record<string, string[]> | null,
  newFilters: Record<string, string[]>,
): Record<string, string[]> {
  if (!existing) return newFilters
  return { ...existing, ...newFilters }
}
```

Use when endpoint has server-side default filters (e.g. `status: ["active"]`).

## api.ts fetch

```typescript
export async function fetchActivityList(params: Record<string, string>) {
  const url = buildApiUrl(`${API_BASE}/api/v1/activities/list`, params)
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) throw new Error(`activities/list ${res.status}`)
  return res.json() as ActivityListResponse
}
```

Types must match backend `IRead` / response envelope from contract.

## TanStack Query keys

```typescript
export const catalogQueryKeys = {
  list: (filters?: string, period?: string) =>
    ["catalog", "list", filters ?? "", period ?? ""] as const,
}
```

Include serialized `filters` and `period` in key — filter change = new cache entry.

## vitest minimum

```typescript
it("maps UI state to filters query param", () => {
  const params = buildQueryParams({ difficulty: "beginner", ... })
  expect(params.filters).toBe('{"difficulty":["beginner"]}')
})

it("uses gt for min price", () => {
  const params = buildQueryParams({ minPrice: 5000, ... })
  expect(params.gt).toBe('{"price__gte":5000}')
})

it("buildListApiFilters uses city__slug join key", () => {
  const f = buildListApiFilters({ city: "sochi", ... })
  expect(f["city__slug"]).toEqual(["sochi"])
})
```

Run: `npm run test -- filters/<domain>`

## URL sync (Next.js)

- `useSearchParams` / `useRouter` — UI state ↔ browser URL ↔ API params
- Apply on filter change or explicit Apply button (dashboard pattern)
