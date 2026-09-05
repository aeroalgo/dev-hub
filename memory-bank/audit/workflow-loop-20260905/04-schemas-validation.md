# 04. Аудит JSON schemas и boundary validation

## 1. Реестр boundary schemas

Текущий `loop/schemas/boundary_registry.py` регистрирует только четыре схемы:

| Schema id | Model | Где используется |
|---|---|---|
| `mb-load-result/v1` | `MbLoadResult` | `mb_load` / MCP load |
| `loop-gate-verdict/v1` | `GateVerdictRecord` | verify/reviewer gate, sidecar |
| `loop-repair-result/v1` | `RepairResultRecord` | gate-repair |
| `loop-validate-result/v1` | `ValidateResult` | результат самого validator |

Отдельно существуют доменные модели YAML/JSON: `loop-handoff/v1`, `loop-state/v2`, `loop-checkpoint/v1`, `epic-decompose/v1`, `epic-implement/v1`, `epic-qa/v1`, `epic-audit/v2`, `loop-sunset-inventory/v1`, workflow pack schemas и incident schemas. Они валидируются разными функциями, а не единой boundary registry.

## 2. P0 — sunset schema фактически недоступна

`loop/schemas/sunset_inventory.py` определяет `SunsetReport`, но:

- `SCHEMA_LOOP_SUNSET_INVENTORY` отсутствует в `BOUNDARY_REGISTRY`;
- `validate_boundary("loop-sunset-inventory/v1", payload)` возвращает `schema_unknown_schema_id` даже для корректного payload;
- `SubagentStop` не вызывает validation branch для sunset;
- тесты проверяют только `SunsetReport.model_validate`, но не end-to-end boundary.

Это даёт ложный контракт: prompt требует вызвать validator, который не может принять заявленную schema.

Исправление: добавить модель в registry, экспорт и tests, затем подключить result к stop handler/sidecar. Если sunset намеренно advisory, удалить из prompt обязательное требование boundary validation.

## 3. Matrix: что сейчас реально проверяется

| Payload | Direct `validate_boundary` | SubagentStop | Sidecar | Semantic checks |
|---|---|---|---|---|
| verify gate JSON fence | да, если fence найден | да | да | частично, позднее через state |
| verify `data.verdict` без fence | нет | принимается без boundary validation | может быть записан | нет |
| gate payload без `schema` | да, проходит из-за default field | может пройти, если остальная форма полна | да | нет |
| repair JSON fence | да | да, retry 1 раз | state only, отдельного typed repair sidecar нет | нет |
| sunset JSON fence | нет: unknown schema | нет | нет | нет |
| Codex collab gate fence | свой lax parser | downstream да | через subagent-stop | частично |
| YAML implement/decompose | отдельные validators | через finish/check-after | state/index | да, но не boundary registry |

## 4. P1 — schema field optional, хотя protocol объявляет его обязательным

В `GateVerdictRecord`, `RepairResultRecord` и `SunsetReport` поле `schema` имеет default. В Pydantic JSON schema оно не попадает в `required`.

Проверенный эффект:

```text
GateVerdictRecord(agent_id, verdict, recorded_at) → valid=True
RepairResultRecord(agent_id, status, recorded_at) → valid=True
```

Для внутреннего typed constructor default удобен. Для внешнего wire protocol он ослабляет идентификацию версии. Нужны разные модели:

- `Wire...` — `schema` required;
- `Internal...` — default допустим только после explicit normalization.

Или включить validator mode `require_discriminator=True`.

## 5. P1 — bypass через hook payload

В `subagent-stop.py` для verify:

```python
if fence_data is not None or not data.get("verdict"):
    val_res = validate_boundary(...)
```

Если runtime передал `data["verdict"] = "PASS"`, а machine JSON fence отсутствует, условие validation пропускается, и verdict обрабатывается. Это противоречит prompt contract “ответ без valid JSON fence = protocol FAIL”.

Правило должно быть прямым:

```text
verify/reviewer completion → valid wire fence обязателен
payload verdict → только hint/transport metadata, не источник истины
```

Проверять и `message`, и payload-derived fields одним typed parser; payload verdict можно использовать только если runtime документирован как trusted machine adapter и имеет отдельный signed/typed envelope.

## 6. P1 — отсутствуют cross-field constraints

Текущие модели в основном проверяют типы, enum и `extra=forbid`. Они не проверяют:

### Gate verdict

- `agent_id` допустим и соответствует known agent;
- `verdict=BLOCKED` разрешён для конкретного agent/phase;
- `step_id/epic_id/session_id` обязательны для loop finish;
- `recorded_at` корректный ISO timestamp;
- `evidence_sha256` действительно sha256;
- payload относится к current gate identity.

### Repair result

- `status=done` требует `remaining_blockers=[]`;
- `status=fail` должен содержать remaining blocker или diagnostic;
- `fixed_blockers` и `remaining_blockers` не должны пересекаться;
- fixed blockers должны быть подмножеством parent FAIL blockers;
- `agent_id` должен быть `gate-repair`;
- repair result должен ссылаться на parent verify evidence/session/step.

### Sunset report

- `end_line >= start_line`;
- item path существует или имеет explicit `missing_path` diagnostic;
- `ok=true` не допускает обязательных unresolved diagnostics;
- `new_sot` и `boundary_id` должны быть привязаны к current epic/transition.

Валидный JSON не обязательно означает валидный transition.

## 7. P1 — несколько parser implementations

Есть как минимум четыре пути разбора gate JSON:

- `validate_boundary()` + `GateVerdictRecord`;
- `_lib.extract_json_fence()` + `extract_verdict()`;
- `parse_gate_verdict_message()` с legacy branch;
- `loop/codex_collab_verdict.py` с `_CollabGateVerdictFence`.

Они различаются:

- `extract_json_fence` допускает info-string после `json`, хотя prompt запрещает;
- repair parser принимает только bare `json`;
- `extract_verdict` допускает schema=None;
- Codex collab model имеет `extra="ignore"`, тогда как canonical model `extra="forbid"`;
- legacy branch может писать sidecar до того, как full boundary validation завершилась.

Нужен единственный `parse_wire_message(kind, text)`, который возвращает typed diagnostic result. Compatibility parser должен быть отдельным explicit legacy adapter с telemetry и deadline удаления.

## 8. P2 — документация registry уже устарела

`loop/schemas/README.md` ссылается на несуществующий `loop/schemas/verdict.py`, на `LoopGateVerdict` и на `SKIP`, хотя фактическая модель — `gate_verdict.py`, `GateVerdictRecord`, `PASS/FAIL/BLOCKED`.

README должен генерироваться из registry или проходить test “каждая таблица schema → реальный module/class/enum”.

## 9. Что добавить в тесты

- registry smoke: каждый `SCHEMA_*` из prompts/agents существует в registry или помечен advisory;
- wire schema requires explicit `schema`;
- malformed/unknown/extra fields для gate, repair, sunset;
- cross-field semantic constraints;
- SubagentStop: fence absent + payload verdict → fail/retry;
- SubagentStop: valid sunset → persisted result;
- Codex collab: same canonical parser, repair and sunset cases;
- sidecar ownership mismatch by agent/step/session/epic;
- mutation tests на bypass condition и retry counters.

## 10. Acceptance criteria

Валидацию можно считать рабочей только когда для каждого declared machine agent выполняется цепочка:

```text
prompt declares schema
  → registry resolves schema
  → parser extracts same wire format
  → shape validation
  → semantic ownership validation
  → sidecar/state persistence
  → stop-gate consumes the same record
```

Сейчас эта цепочка гарантирована только частично для software verify/repair и не гарантирована для sunset/video.
