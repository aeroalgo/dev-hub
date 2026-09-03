# YAML-CONTRACT — lint для epic shard + decompose index (opt-in)

Поля **`epic-decompose/v1`** (единственный канон shard), `epic-implement/v1`, `decompose-formula/v1` (`loop/schemas/formula.py`), qa/refactor/security.  
**FORBIDDEN** invented decompose schemas: `epic-decompose-shard/*`, `epic-decompose-step/*`, любые имена кроме template.  
Read-time alias только `integ-decompose/v1` → нормализуется в `epic-decompose/v1` (не писать legacy в файлы).  
Шаблон: `.cursor/templates/decompose/epic-step.yaml`.  
**Не** часть runner hot path для одного шага. Opt-in:

```bash
python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>
python3 .claude/hooks/epic_resolve.py validate-decompose-tree --decompose <decompose-dir|index.yaml>
python3 .claude/hooks/epic_resolve.py verify-decompose-creative --decompose <decompose-dir|index.yaml>
```

`validate-decompose-tree` — **DECOMPOSE FINISH fail-closed** (stop-gate): schema load всех sNN|eNN (`epic-decompose/v1`). Полный lint verify — `validate-step`.

`verify-decompose-creative` — **advisory** (exit 0 всегда): сверка plan `CREATIVE need` ↔ shard `needs_creative` / creative-артефакты; JSON `verdict` + `gaps`/`missing`/`fix` для агента. Не блокирует stop-gate.

Шаг YAML = ТЗ агенту (цель, файлы, tests).

## Decompose index — yaml канон, md зеркало

| Файл | Роль |
|------|------|
| `plan/decompose-*/index.yaml` | **единственный SoT** очереди + `status`; prepare / identity / IMPLEMENT |
| `plan/decompose-*/index.md` | human coverage (DECOMPOSE/AUDIT); status = best-effort зеркало |

Курсор = `activeContext.md` + `index.yaml` + step yaml.  
Md **не** fail-closed gate. Рассинхрон → deterministic `repair-index-mirror` (prepare/check_after вызывают автоматически; CLI вручную).

**Fingerprint stall** (агент вышел без смены Handoff): `check-after` → `repair_fingerprint_stall`. Если implement ready (checkpoints + files на диске) → finalize/re-arm без LLM. Иначе **outer retry** (новый агент, prompt со stall-блоком) до `EPIC_DEGRADED_MAX`; после лимита → `NEED_HUMAN` HALT.

**Cursor SoT = `index.yaml` only.** На `prepare` вызывается `sync_cursor_from_index`: `activeContext` + `armed_step` переписываются из next pending; stale checkpoint с другим step сбрасывается. `armed_step` — кэш, не источник правды.

**Одна точка записи status** (не править md и yaml руками):

```bash
python3 .claude/hooks/epic_resolve.py finalize-step \
  --decompose decompose-v1-portal --step e22
```

`finalize-step` также пишет `tasks/log` и при смене фазы — `tasks.md`.

После смены состава шагов в `index.md` (новые строки таблицы) или если md битый:

```bash
python3 .claude/hooks/epic_resolve.py repair-index-mirror \
  --decompose decompose-v1-portal
python3 .claude/hooks/epic_resolve.py sync-index-yaml \
  --decompose decompose-v1-portal
```

`repair-index-mirror` пересобирает queue-таблицу md из yaml (не трогает yaml).  
`sync-index-yaml` по умолчанию **сохраняет** status из yaml; `--from-md-status` — bootstrap из md (только bootstrap).

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

`validate-decompose-tree` дополнительно: каждый shard имеет `plan_contract`; index.md Notes без bare deferred.
