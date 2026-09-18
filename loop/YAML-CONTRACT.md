# YAML-CONTRACT — lint для epic shard + decompose index (opt-in)

Поля **`epic-decompose/v1`** (единственный канон shard), `epic-implement/v1`, `decompose-formula/v1` (`loop/schemas/formula.py`), qa/refactor/security.  
**FORBIDDEN** invented decompose schemas: `epic-decompose-shard/*`, `epic-decompose-step/*`, любые имена кроме template.  
Read-time alias только `integ-decompose/v1` → нормализуется в `epic-decompose/v1` (не писать legacy в файлы).  
Шаблон: `.cursor/templates/decompose/epic-step.yaml`.  
**Не** часть runner hot path для одного шага. Opt-in:

```bash
python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>
python3 .claude/hooks/epic_resolve.py validate-decompose-tree --decompose <epic-dir|yaml/decompose-index.yaml>
python3 .claude/hooks/epic_resolve.py verify-decompose-creative --decompose <epic-dir|yaml/decompose-index.yaml>
```

`validate-decompose-tree` — **DECOMPOSE FINISH fail-closed** (stop-gate): schema load всех sNN|eNN (`epic-decompose/v1`). Полный lint verify — `validate-step`.

`verify-decompose-creative` — **advisory** (exit 0 всегда): сверка plan `CREATIVE need` ↔ shard `needs_creative` / creative-артефакты; JSON `verdict` + `gaps`/`missing`/`fix` для агента. Не блокирует stop-gate.

Шаг YAML = ТЗ агенту (цель, файлы, tests).

## Layout v2 & Decompose index — YAML-only

| Файл (Layout v2) | Роль |
|------|------|
| `plan/<epic_id>/yaml/decompose-index.yaml` | **единственный SoT** очереди + `status`; prepare / identity / IMPLEMENT |
| `plan/<epic_id>/yaml/steps/sNN-*.yaml` | decompose step shards |
| `implement/<epic_id>/sNN-*.yaml` | implement step shards (**без** `yaml/` — split только у plan/decompose) |
| `qa|audit|analyze/<epic_id>/*.yaml` | phase artifacts (**без** `yaml/` subdir) |

**Scaffold contract (HARD):**
- Scaffolding шагов выполняется исключительно через `mb-scaffold` (`mb-scaffold plan`, `mb-scaffold decompose`, `mb-scaffold implement`).
- **FORBIDDEN:** Write scaffolded step files from scratch (только Edit).

Курсор = `activeContext.md` + `yaml/decompose-index.yaml` + step yaml.
YAML-индекс валидируется Pydantic-контрактом и является единственным fail-closed источником очереди.

**Fingerprint stall** (агент вышел без смены Handoff): `check-after` → `repair_fingerprint_stall`. Если implement ready (checkpoints + files на диске) → finalize/re-arm без LLM. Иначе проверяется fingerprint scoped-файлов текущего шага: реальное изменение файлов сбрасывает stall-счётчик и запускает outer retry с dirty-контекстом; только отсутствие и Handoff, и scoped-прогресса считается повторным stall и идёт до `EPIC_DEGRADED_MAX`, после лимита → `NEED_HUMAN` HALT.

**Cursor SoT = `yaml/decompose-index.yaml` only.** На `prepare` вызывается `sync_cursor_from_index`: `activeContext` + `armed_step` переписываются из next pending; stale checkpoint с другим step сбрасывается. `armed_step` — кэш, не источник правды.

**Одна точка записи status** (не править md и yaml руками):

```bash
python3 .claude/hooks/epic_resolve.py finalize-step \
  --decompose memory-bank/back/plan/T-HUB-001/yaml/decompose-index.yaml --step s01
```

`finalize-step` также пишет `tasks/log` и при смене фазы — `tasks.md`.

Состав шагов меняется только через валидированный `yaml/decompose-index.yaml` и shards
`yaml/steps/`; отдельных markdown-индексов и mirror/bootstrap-команд нет.

## Traceability fields

Поля трассируемости шагов (`epic-decompose/v1` и `epic-implement/v1`):

- **`plan_refs`** (`list[str]`, required на decompose-shards): ссылки на требования/пункты плана (например `"plan-T-HUB-024 FR-011"`). Каждое requirement ID из плана должно покрываться хотя бы одним `plan_refs` или **валидным** `out_of_scope`.
- **`plan_contract`** (`dict`, **required** на decompose-shards): `fr_ids` · `nouns` · `layout_paths` · `ac_quotes` · `plan_jumps` — bake plan WHAT для IMPLEMENT. `validate-decompose-tree` fail-closed без блока.
- **`out_of_scope`** (`list[str]`, optional): пропуск/соседний шаг. Строки с `deferred`/`partial`/`follow-up` **без** `follow_up: T-…` → **CRITICAL** в `validate-traceability` и **не** считаются coverage.
- **`evidence.files`** / **`evidence.tests`** / **`status`** — как раньше для implement.

### Валидация трассируемости (`validate-traceability`)

| Поле | Тип | Условие / Ошибка | Severity |
|------|-----|------------------|----------|
| `plan_refs` / `out_of_scope` | `list[str]` | Requirement не в plan_refs и не в **валидном** out_of_scope | CRITICAL |
| `out_of_scope` deferral | `list[str]` | deferred/partial/follow-up без `follow_up: T-…` | CRITICAL |
| `plan_refs` & `out_of_scope` | `list[str]` | Оба пустые | HIGH / CRITICAL (--strict) |
| `evidence.tests` | `list[str]` | completed без tests | HIGH / CRITICAL (--strict) |
| `@pytest.mark.ac` | marker | нет AC markers | MEDIUM / HIGH (--strict) |

`validate-decompose-tree` дополнительно: каждый shard имеет `plan_contract`; YAML index/shards без bare deferred.
