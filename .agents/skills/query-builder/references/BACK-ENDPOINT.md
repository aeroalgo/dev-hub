# BACK endpoint bootstrap

## File order (TDD)

1. `app/<entity>/schema.py` — `IFilter`, `ISearch`, `ISort`, `IRead` (+ `get_table_mapping` if table)
2. `api/v1/endpoints/<entity>.py` — `mapping_filters`, `PaginateQueryParams.update`, `GET /list`
3. `tests/api/test_<entity>.py` — red tests first

## Endpoint template

```python
mapping_filters = {
    "city": {
        "model": [City],
        "filter": CityIFilter,
        "path": [(Activity.city_id, City.id, City)],
    },
}

EntityPaginateQueryParams = PaginateQueryParams.update(
    search=ISearch,
    filter=IFilter,
    sort=ISort,
    read=IRead,
    model="Activity",
    mapping_filters=mapping_filters,
    period_mode="created_at",
)

@router.get("/list")
async def list_entities(
    query_params: Annotated[EntityPaginateQueryParams, Depends(EntityPaginateQueryParams)],
    db: Session = Depends(get_session),
):
    data = await crud.activity.get_multi(
        db=db, query_params=query_params, mapping_filters=mapping_filters
    )
    meta = {"read_table_mapping": IRead.get_table_mapping()} if query_params.meta else {}
    return IGetResponseBase(data=data, meta=meta)
```

## pytest minimum

```python
def test_list_filter_difficulty(client):
    r = client.get('/api/v1/activities/list?filters={"difficulty":["beginner"]}')
    assert r.status_code == 200

def test_list_join_filter(client):
    r = client.get('/api/v1/activities/list?filters={"city__slug":["sochi"]}')
    assert r.status_code == 200

def test_list_invalid_filter(client):
    r = client.get('/api/v1/activities/list?filters={"unknown":["x"]}')
    assert r.status_code == 422

def test_list_period(client):
    r = client.get('/api/v1/activities/list?period="2025-01-01:2025-12-31"')
    assert r.status_code == 200

def test_list_price_range(client):
    r = client.get(
        '/api/v1/activities/list?gt={"price__gte":1000}&lt={"price__lte":5000}'
    )
    assert r.status_code == 200

def test_list_pagination(client):
    r = client.get("/api/v1/activities/list?page=1&size=20")
    assert r.status_code == 200
```

Run: `poetry run pytest tests/api/test_<entity>.py --run-integration`

## Response meta (table UI)

```python
meta = {
    "table_name": "activity",
    "read_table_mapping": IRead.get_table_mapping(),
}
```

Front table columns ↔ `read_table_mapping` keys (§0.11 grep).

## Default filters

If endpoint requires baseline filter (e.g. `status=["active"]`):
- Merge in service or document as `default_filters` in contract
- Front: `mergeFilters(defaultFilters, uiFilters)` before `JSON.stringify`

## Verification

- [ ] No raw SQL / manual `where()` in list handler
- [ ] `crud.get_multi` → `build_query` → QueryBuilder
- [ ] All contract filter keys covered by IFilter / mapping_filters
