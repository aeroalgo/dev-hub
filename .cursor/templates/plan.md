# [T-xxx | slug] PLAN

**Дата:** YYYY-MM-DD  
**Режим:** BACK PLAN | FRONT PLAN | PM PLAN  
**Уровень:** L1–L4  
**Статус:** draft | active | done

## Контекст

- req: …
- deps: T-xxx / gap ref
- refs: …

→ [decompose-…/index.md](decompose-…/index.md) — **после DECOMPOSE:** единственный трекер шагов (не дублировать s01…sNN здесь)

## Продуктовая спека (WHAT)

> WHAT описывает пользовательскую проблему, ожидаемые outcomes и границы продукта. Не включать стек, имена модулей, API или детали реализации — они относятся к HOW.

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как <персона>, я хочу <действие>, чтобы <результат>. | P0 | <как проверить story отдельно от остальных> |
| US-002 | Как <персона>, я хочу <действие>, чтобы <результат>. | P1 | <независимая проверка> |

Для каждой story P0/P1 добавить Acceptance Scenarios в формате Given / When / Then. Не подменять независимый тест общим smoke-тестом плана.

#### Acceptance Scenarios — US-001

- **Given:** <исходное состояние и условия>
- **When:** <действие пользователя или системы>
- **Then:** <наблюдаемый результат>

### Functional Requirements (FR-###)

- **FR-001:** Система должна <измеримое функциональное поведение>.
- **FR-002:** Система должна <измеримое функциональное поведение>.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | <метрика, порог и период измерения> | <как и где измеряется> | outcome |
| SC-002 | <метрика, порог и период измерения> | <как и где измеряется> | outcome |

### Assumptions

- <документированное допущение, зависимость или граница scope>.
- <что считается истинным до уточнения и как это влияет на WHAT>.

### Clarifications

- Session: <дата / участники / ссылка на `clarify-*.md` или `n/a`>.
- Решённые вопросы и принятые изменения: <ссылка на запись или `n/a`>.

### [НУЖНО УТОЧНИТЬ]

- [НУЖНО УТОЧНИТЬ] <вопрос, блокирующий точное решение; после PLAN удалить или перенести в defer>.

## AC

1. …
2. …

### AC− (обязательны при brownfield replace / cutover)

1. Нет второго entrypoint на ту же роль.
2. Нет soft default URL/host на чужой сервис.
3. Misconfig → fail at start, не stub / silent success.
4. Нет prod dual-path new+legacy без follow-up epic в roadmap queue.

Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

## Техника / архитектура (HOW)

> HOW описывает техническую стратегию и границы реализации отдельно от WHAT.

- Стек и инфраструктура: …
- Модули, интеграции и контракты: …
- Ограничения реализации и наблюдаемость: …

## Replacement / sunset (brownfield)

> Эпик **заменяет** runtime → заполнить **A + B + C**. DECOMPOSE → `deletes` + финальный `*-legacy-fallback-purge`. Greenfield → `n/a` во всех трёх.  
> Policy: `delete in-epic` (default) | `shim+follow-up` (**только** с epic ID уже в `.queue.yaml`) | `keep` (только с ADR). **`fallback` как policy — FORBIDDEN.**  
> Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| … | … | delete in-epic |
| n/a | — | greenfield |

### B. Entrypoints / deploy

| Устаревает (compose service / CMD / CLI) | Замена | Policy |
| :--- | :--- | :--- |
| … | … | delete in-epic |
| n/a | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает (pattern / default / stub) | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| … | raise / non-zero exit | delete in-epic |
| n/a | — | greenfield |

## До DECOMPOSE (черновик нарезки)

Краткий outline фаз **без** checkbox-статусов (статусы появятся только в decompose index).  
После DECOMPOSE — этот блок сжать или удалить; детали → `sNN-*.yaml`.  
Brownfield: в конце очереди заложить `sNN-legacy-fallback-purge`.

## Следующий режим

→ BACK/FRONT DECOMPOSE | CREATIVE | IMPLEMENT
