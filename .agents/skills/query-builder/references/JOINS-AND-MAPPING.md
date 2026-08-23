# Joins and mapping_filters

## Join notation

HTTP filter key `relation__column`:
1. Split on first `__` → `relation`, `column`
2. Lookup `mapping_filters[relation]`
3. Use `path` tuple chain for JOIN
4. Validate value against `mapping_filters[relation].filter` (RelationIFilter)

Flat field `difficulty` → root model `IFilter`, no join.

## mapping_filters structure

```python
mapping_filters = {
    "city": {
        "model": [City],
        "filter": CityIFilter,
        "path": [
            (Activity.city_id, City.id, City),
        ],
    },
    "emotion": {
        "model": [Emotion],
        "filter": EmotionIFilter,
        "path": [
            (Activity.id, LinkActivityEmotion.activity_id, LinkActivityEmotion),
            (LinkActivityEmotion.emotion_id, Emotion.id, Emotion),
        ],
    },
    "transcription": {
        "model": [Transcription],
        "filter": TranscriptionIFilter,
        "path": [
            (Agent.id, Call.agent_id, Call),
            (Call.id, Transcription.call_id, Transcription),
        ],
    },
}
```

Each `path` entry: `(left_column, right_column, target_model)`.

## PaginateQueryParams.update()

```python
EntityPaginateQueryParams = PaginateQueryParams.update(
    search=ISearch,
    filter=IFilter,
    sort=ISort,
    read=IRead,
    model="Activity",
    mapping_filters=mapping_filters,
    period_mode="created_at",
)
```

## schema.py — IFilter

- Flat fields on root `IFilter` = keys in `filters` JSON without `__`
- Join fields use key `relation__field`; validated via `mapping_filters[relation].filter`
- `IRead.get_table_mapping()` for table UI meta

## _parse_join_column (schema.py behavior)

```python
# "city__slug" → model=City, column="slug", path from mapping_filters["city"]
# "difficulty" → root model from config.model, column="difficulty"
```

## _validate_filter

- Unknown key or invalid value → `ValidationException` → 422
- pytest must assert 422 for `?filters={"unknown":["x"]}`

## Checklist per endpoint

- [ ] Every `__` key in contract has `mapping_filters` entry with `path`
- [ ] `RelationIFilter` fields match contract keys (suffix after `__`)
- [ ] Root `IFilter` fields match flat keys
- [ ] Join path reaches correct table for filter column
