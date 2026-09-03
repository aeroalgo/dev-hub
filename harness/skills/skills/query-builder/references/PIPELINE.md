# Pipeline — PaginateQueryParams → QueryBuilder → SQL

** paths:** `core/base/schema.py`, `core/base/query_builder.py`, `core/base/crud.py`

## HTTP → SQL flow

```
HTTP query string
  → PaginateQueryParams validators (schema.py)
  → rows: { model, column, value, path, join_type }
  → QueryContext
  → QueryBuilder.build()
  → SQLAlchemy Select
  → crud.get_multi()
```

## QueryBuilder.build() steps

```
init → soft_delete → visibility → id/params
     → joins → joined_models_soft_delete → loader_options → finalize
```

| Step | Purpose |
|------|---------|
| `_apply_soft_delete` | `deleted_at IS NULL` (unless `records=all`) |
| `_apply_search` | ILIKE OR on search columns |
| `_apply_period` | `[start, end+1day)` on `period_mode` column |
| `_apply_numeric_filters` | `gt`/`lt`/`eq` → `>=`/`<=`/`==` |
| `_apply_generic_filters` | `filters` → `IN (...)` or `ARRAY.any()` |
| `_apply_sorting` | ascending/descending; default `created_at DESC` |
| `_apply_joins` | path from `mapping_filters` |
| `_apply_loader_options` | selectinload + soft delete on relations |

## PaginateQueryParams output row

After `validator_filters`, each filter becomes:

```python
{
    "column": "slug",
    "value": ["sochi"],
    "model": City,
    "path": [(Activity.city_id, City.id, City)],
    "join_type": None,
}
```

Invalid key → `ValidationException` → HTTP 422.

## crud.build_query()

```python
qb = QueryBuilder(separate_nulls=self.__separate_nulls)
ctx = QueryContext(
    model=self.model,
    query_params=query_params,
    mapping_filters=mapping_filters,
)
return qb.build(ctx)
```

## Endpoint rule

**Forbidden:** manual `select()` / `where()` in list endpoint — only `PaginateQueryParams` + `crud.get_multi(..., mapping_filters=...)`.
