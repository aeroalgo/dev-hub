# plan-INTEG-<task_id>

**Дата:** YYYY-MM-DD  
**Режим:** INTEG PLAN  
**Scope:** portal | journey | section  
**Домен/slug:** <portal-journey-slug>  
**Статус:** draft | active | done  
**Gap ref (опционально):** [gap-YYYYMMDD-<slug>.md](../gap/<epic_id>/gap-YYYYMMDD-<slug>.md)

→ [decompose-<plan_id>/index.md](decompose-<plan_id>/index.md) — **после DECOMPOSE:** единственный трекер status `eNN` (не дублировать `- [ ] e01…` в этом plan)

## Суть

Master-план wire **всего портала** (или указанного section): каждый route, UI-элемент, API-вызов к БД. Движение — по элементам страниц, не по слоям BACK/FRONT.

## Продуктовая спека (WHAT)

> Компактная WHAT-секция для portal plan: фиксирует user journey goals и измеримые результаты без стека, API или деталей реализации. Portal plan остаётся element-centric, не story-centric.

- **User journey goals:** <какой пользовательский результат должен быть достигнут>.
- **Ключевые Success Criteria (SC-###):** <измеримые метрики, пороги и период измерения>.
- **Assumptions:** <допущения, scope boundaries и зависимости>.

### Clarifications

- Session: <дата / участники / ссылка на `clarify-*.md` или `n/a`>.
- Вопросы по route/element и принятые решения: <ссылка или `n/a`>.
- [НУЖНО УТОЧНИТЬ] <неопределённость, влияющая на element registry или journey>.

## Element registry (as-built)

> WHAT выше задаёт outcomes; registry ниже сохраняет element-centric wire и portal inventory без изменения его статусов и rollout.

> Источник: routes `frontend/src/app/**` + components + `back/implement/` + `front/implement/` — **не** gap/, contracts/, plan/decompose shards.
> После таблицы — **обязательны** секции `## Element eNN — …` для каждого P0/P1 (не ограничиваться одной таблицей).
> Registry + per-element §§ = **стратегия/as-built**, не runtime-трекер done/pending.

| route | UI element (component) | data need | API today | BACK implement | FRONT implement | priority |
|-------|------------------------|-----------|-----------|----------------|-----------------|----------|
| `/` | `Hero` — поиск города | redirect city | none / mock | — | implement-… | P0 |
| `/catalog` | `FilterBar` + list | activities list | ❌ mock | pending | implement-… | P0 |

**Legend API today:** ✅ live | ❌ missing | ⚠️ mock fallback | — static

## Element e01 — <title> (повторить на каждый P0/P1)

### §UI
- route, component path(s)

### §Data need
- …

### §API today
- ✅ / ⚠️ / ❌ + real path

### §Contract outline
```
METHOD /path
request…
response…
```

### §BACK / §FRONT wire
- …

### §Verify
- §0.11 pair + test cmd


## API inventory

| Method | Path | DB tables | Consumer element(s) | Status |
|--------|------|-----------|---------------------|--------|
| GET | `/api/v1/activities` | activity, city | FilterBar, ActivityShowcase | ❌ |

## User journeys (E2E)

| ID | Persona | Path | Elements touched |
|----|---------|------|------------------|
| J1 | Guest | Home → Catalog → Activity | e01, e04, e06 |
| J2 | Client | Slot → Checkout → Dashboard | e07, e10, e11 |

## Rollout (by UI element, not by layer)

> Порядок фаз — стратегия. **Не** ставить `- [ ]` / `done` здесь. Статус элементов → `decompose/index.md` после DECOMPOSE.

**Фаза 0 — Discovery (guest funnel)**
1. e04 catalog list + filters
2. e06 activity detail + e07 booking widget

**Фаза 1 — Transaction**
3. e09 auth gate
4. e10 checkout

**Фаза 2 — Portals**
5. e11 client bookings
6. e16 provider scheduler …

## Test matrix

| Journey | BACK pytest | FRONT vitest | Wire / E2E |
|---------|-------------|--------------|------------|
| J1 | test_activities | catalog-filters.test | Playwright catalog |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mock in ActivityShowcase | false green home | e03 wire first |

## Replacement / sunset (brownfield)

> Mock/legacy clients, stub fetch, дублирующие wire-пути, entrypoints, soft-fail, **instruction surfaces**. DECOMPOSE → ladder add→wire→enforce→purge + `deletes` + финальный purge. Нет замен → `n/a` во всех четырёх.  
> Policy: `delete in-epic` (default) | `shim+follow-up` (только epic ID в `.queue.yaml`) | `keep` (+ADR). **`fallback` FORBIDDEN.**  
> Wire-complete: sole SoT (@.cursor/rules/shared/workflow-behavior-first.mdc §3).  
> Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

### A. Code / modules / mocks

| Устаревает (path / symbol / mock) | Element(s) | Замена | Policy |
| :--- | :--- | :--- | :--- |
| `frontend/.../mock-…` | e0N | live client | delete in-epic |
| n/a | — | — | all live / greenfield |

### B. Entrypoints / deploy

| Устаревает (compose / script / dual route) | Element(s) | Замена | Policy |
| :--- | :--- | :--- | :--- |
| … | e0N | … | delete in-epic |
| n/a | — | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает (mock branch / default) | Element(s) | Замена (fail-closed) | Policy |
| :--- | :--- | :--- | :--- |
| prod mock рядом с live | e0N | delete mock | delete in-epic |
| n/a | — | — | greenfield |

### I. Instruction surfaces

| Устаревает (prompt / rule / agent text) | Element(s) | Замена | Policy |
| :--- | :--- | :--- | :--- |
| … | e0N | live SoT instruction | delete in-epic |
| n/a | — | — | greenfield |

## Handoff

- **Done:** …
- **Files:** этот plan
- **Next:** INTEG DECOMPOSE (element-first `eNN-*.yaml`)
- **New chat:** yes
