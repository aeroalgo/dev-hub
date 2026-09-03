# BACK↔FRONT Gap Analysis — implement-папки

**Дата:** YYYY-MM-DD  
**Режим:** INTEG GAP  
**Статус:** open | active | closed  
**Slug:** <domain-or-scope>  
**Триггер:** <почему запущен GAP — цитата/ссылка на §Gaps implement>  
**Путь (epic):** `memory-bank/integration/gap/<epic_id>/gap-YYYYMMDD-<slug>.md`  
**Путь (ad-hoc):** `memory-bank/integration/gap/gap-YYYYMMDD-<slug>.md`  
**Source implement (если scoped):** [implement-….md](../../implement/implement-<epic_id>/…)

## Links (для INTEG GAP CLOSE)

Relative из `gap/<epic_id>/` (из корня `gap/` — на один `../` меньше).

| Kind | Artifact |
|------|----------|
| Source implement | [implement-….md](../../implement/implement-<epic_id>/…) |
| BACK plan / covered_by | [plan-BACK-….md](../../../back/plan/…) → [decompose-…/index.md](../../../back/plan/decompose-…/index.md) |
| FRONT plan | [plan-FRONT-….md](../../../front/plan/…) → [decompose-…/index.md](…) |

## Методология

- Источник BACK: `memory-bank/back/implement/` (N артефактов)
- Источник FRONT: `memory-bank/front/implement/` (M артефактов)
- Верификация кода: grep endpoints в `api/`, `frontend/src/lib/*-api.ts`
- Планы закрытия: `back/plan/plan-BACK-GAP-…`, `front/plan/plan-FRONT-GAP-…`, `covered_by` epic
- **Обязательно:** секция **«Работы по gap»** — не только таблица ID; для каждого G-* подробно что сделать
- Runtime contract: BACK/FRONT/INTEG read the same `activeContext.md` + decompose index source of truth; `state.json` is telemetry projection, not a durable cursor.
- Gap metadata must preserve role, `decompose`, `depends_on`, completion/checkpoint and v1 compatibility diagnostics. Dependency work is sequential in one checkout; `GAP_FANOUT` is manual-only unless the runner explicitly reports otherwise.
- Rollout evidence must cover timeout/process death, `BLOCKED`/`NEED_HUMAN`, validated `resume_from_step` and rollback without resetting to first pending.

---

## 1. Матрица паритетности (домен → BACK → FRONT)

| Домен | BACK implement | FRONT implement | Паритет | Действие |
|-------|----------------|-----------------|---------|----------|
| | | | ✅ / ⚠️ / ❌ / N/A | |

---

## 2. BACK есть → FRONT нет / частично (G-B→F)

### 2.N <Домен> (<BACK implement ref>)

**BACK:** …  
**FRONT:** …

| Gap ID | Что на BACK | Чего нет на FRONT | Plan | Status |
|--------|-------------|-------------------|------|--------|
| G-BF01 | | | plan-FRONT-GAP-… | open |

→ [plan-FRONT-GAP-…](../../../front/plan/plan-FRONT-GAP-….md)  
→ decompose: [index.md](../../../front/plan/decompose-…/index.md) (если есть)

---

## 3. FRONT есть → BACK нет / частично (G-F→B)

### 3.N <Домен> (<FRONT implement ref>)

**FRONT ожидает:**

| Endpoint / поле | Файл | BACK статус |
|-----------------|------|-------------|
| | | ❌ / ⚠️ / ✅ |

**FRONT fallback:** mock / offline

| Gap ID | Что на FRONT | Чего нет на BACK | Plan | Status |
|--------|--------------|------------------|------|--------|
| G-FB01 | | | plan-BACK-GAP-… | open |

→ [plan-BACK-GAP-…](../../../back/plan/plan-BACK-GAP-….md)  
→ decompose: [index.md](../../../back/plan/decompose-…/index.md)

---

## 4. Работы по gap (ОБЯЗАТЕЛЬНО — подробно)

> Нельзя оставить только строку в таблице 2/3. Каждый `G-*` из реестра — отдельный подраздел ниже.  
> Уровень детализации: **средний** — что сломано / асимметрия → что сделать по ролям → критерии done.  
> Источник буллетов из implement §Gaps **переносится сюда** и раскрывается (implement после GAP хранит только link).

### G-BF01 / G-FB01 — <короткий заголовок>

**Асимметрия / что сломано сейчас**

- As-is BACK: <файл / endpoint / поле / поведение>
- As-is FRONT: <файл / UI / маппинг / mock>
- Симптом для пользователя / wire: <что не работает на элементе>

**Что сделать**

| Роль | Действия (конкретно) | Файлы / артефакты |
|------|----------------------|-------------------|
| BACK | … или `n/a` | path или plan/decompose step |
| FRONT | … или `n/a` | path или plan/decompose step |
| INTEG | rewire / проверка после CLOSE | source implement Element Ref |

**Критерии done (этот gap)**

- [ ] <проверяемое условие 1 — код/контракт>
- [ ] <проверяемое условие 2 — UI/grep §0.11>
- [ ] Plan/decompose step закрыт или `covered_by` отмечен done

**Зависимости:** <G-* / MEDIA-S3 / нет>

---

### G-… — <следующий gap>

(повторить блок для **каждого** G-BF / G-FB)

---

## 5. Accepted design (не plan)

| ID | Описание | Почему ok |
|----|----------|-----------|
| A-01 | | |

---

## 6. Сводка расхождений

| Направление | Кол-во gap | Plan-артефакт |
|-------------|-----------|---------------|
| BACK → FRONT | | plan-FRONT-GAP-… |
| FRONT → BACK | | plan-BACK-GAP-… |

---

## 7. Порядок закрытия (рекомендация)

```mermaid
graph LR
  A[шаг 1] --> B[шаг 2]
```

1. …
2. …

---

## 8. Следующие команды

| Роль | Команда | Артефакт |
|------|---------|----------|
| BACK | `BACK IMPLEMENT …` | … |
| FRONT | `FRONT IMPLEMENT …` | … |
| INTEG | `INTEG GAP CLOSE` `@implement-…` | после закрытия слоёв |

## Handoff

- **Done:** сверка; матрица; Y gap ID; §4 работы по каждому G-*; §Gaps в source implement → link.
- **Files:** этот файл + plan-BACK-GAP + plan-FRONT-GAP (если созданы).
- **Next:** BACK/FRONT по §4 → `INTEG GAP CLOSE`
- **New chat:** yes
