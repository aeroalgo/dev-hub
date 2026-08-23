# Dashboard pattern — N APIs, shared UI filters

Use when one FilterBar drives multiple backend endpoints (metrics, list, stats).

## Architecture

```
FilterBar UI
  → context (tempFilters vs applied filters)
  → per-hook filter builder (different API keys!)
  → parallel useQuery fetches
  → TanStack invalidate on Apply
```

## Context: temp vs applied

```typescript
interface DashboardContextType {
  filters: DashboardFilterState       // applied — used in API calls
  tempFilters: DashboardFilterState   // UI only until Apply
  setTempFilter: (name, value) => void
  applyFilters: () => void
  queryParams: { filters?: string; period?: string }
}
```

**Why:** avoid N API calls on every dropdown keystroke; batch on Apply.

## Parallel fetch with different builders

Same UI `country` → different keys per API:

```typescript
// Hook overview metrics
const callFilters = buildCallApiFiltersForDashboard(filters)
const callParams = { filters: JSON.stringify(callFilters), period: queryParams.period }

const transcriptionFilters = buildTranscriptionApiFiltersForDashboard(filters)
const transcriptionParams = { filters: JSON.stringify(transcriptionFilters), period: queryParams.period }

await Promise.all([
  fetch(buildApiUrl(`${API}/call/list`, callParams)),
  fetch(buildApiUrl(`${API}/transcription/list`, transcriptionParams)),
])
```

## Query keys (dashboard)

```typescript
export const DASHBOARD_QUERY_ROOT = ["dashboard"] as const

export const dashboardQueryKeys = {
  overviewMetrics: (filters?: string, period?: string) =>
    [...DASHBOARD_QUERY_ROOT, "overviewMetrics", filters ?? "", period ?? ""] as const,
}

export const dashboardQueryOptions = {
  staleTime: 5 * 60 * 1000,
  refetchOnWindowFocus: false,
} as const

export function invalidateDashboardQueries(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_ROOT })
}
```

On Apply: `applyFilters()` → copy temp → applied → `invalidateDashboardQueries`.

## Extra query params

Document in contract (e.g. `scored_only=true` for chart endpoints):

```typescript
buildApiUrl(base, { ...queryParams, scored_only: "true" })
```

## E2E smoke (Playwright)

1. Load dashboard — wait for initial API 200
2. Change filter in UI — **no** API until Apply (if temp/apply pattern)
3. Click Apply — network requests include `filters=` in URL
4. Assert multiple endpoints called with filters

##  mapping

| Pattern | Path |
|---------|------|
| Filter utils | `frontend/src/lib/filters/<domain>-filters.ts` |
| Query keys | `frontend/src/lib/query-keys/<domain>.ts` |
| Context | `frontend/src/contexts/` or page-local state for simpler cases |
| Hooks | `frontend/src/hooks/use-<domain>.ts` |

Prefer simpler page-local state for L1–L2; full context for L3+ dashboard.
