# INTEG checklist — QueryBuilder wire verification

Use in INTEG QA and finish of INTEG IMPLEMENT (§0.11).

## Contract

- [ ] `memory-bank/integration/contracts/<slug>.md` exists
- [ ] Filter key matrix complete per endpoint variant
- [ ] §0.11 pairs list back file ↔ front file with implement ref

## BACK

- [ ] `mapping_filters` covers all `__` keys from contract
- [ ] `IFilter` / `RelationIFilter` fields = contract keys
- [ ] `PaginateQueryParams.update(...)` on endpoint
- [ ] List handler uses `crud.get_multi` → `build_query` — no raw SQL
- [ ] pytest: filters JSON → 200
- [ ] pytest: join filter → 200
- [ ] pytest: invalid key → 422
- [ ] pytest: period → 200
- [ ] pytest: gt/lt (if numeric filters) → 200
- [ ] pytest: pagination page/size → 200
- [ ] `meta.read_table_mapping` if table UI

## FRONT

- [ ] `lib/api/<domain>.ts` types match `IRead` / response envelope
- [ ] `lib/filters/<domain>-filters.ts` — param types match contract (`filters` vs `gt`/`lt`)
- [ ] Separate builders if endpoints differ (see FILTER-KEY-MATRIX.md)
- [ ] `lib/query-keys/<domain>.ts` includes serialized filters + period
- [ ] vitest: UI state → correct query string
- [ ] vitest: per-endpoint builder → correct keys
- [ ] No filters JSON built inside components

## Wire (grep)

| Check | Command pattern |
|-------|-----------------|
| Endpoint → fetch | grep `/api/v1/<resource>/list` in back + front |
| Filter key | grep key in `IFilter` + `filter-utils` + contract |
| mapping_filters | grep relation name in endpoint + contract join path |
| ENV | `NEXT_PUBLIC_API_URL` ↔ settings |
| meta columns | grep `read_table_mapping` key ↔ table column component |

## Contract drift

Compare contract.md vs code:
- Missing key in IFilter → FAIL
- Front builder uses key not in contract → FAIL
- Extra mapping_filters relation not in contract → FAIL (or update contract)

## Test commands

```bash
poetry run pytest tests/api/test_<entity>.py --run-integration
npm run test -- filters/<domain>
# E2E if UI wired:
npm run test:e2e -- dashboard-filters
```

## PASS → INTEG REFLECT | FAIL → INTEG BUGFIX

On FAIL: fix root cause, update contract if keys changed, re-run checklist.

## Implement registry (as-built)

Source: `memory-bank/back/implement/` + `memory-bank/front/implement/` — not plan shards.
