# [T-xxx | slug] PLAN

**Дата:** YYYY-MM-DD  
**Режим:** BACK PLAN | FRONT PLAN | PM PLAN  
**Уровень:** L1–L4  
**Статус:** draft | active | done  
**Clarify:** `memory-bank/{role}/clarify/clarify-…md` | Phase 0 skipped — taxonomy clear | n/a

## Контекст

- req: …
- deps: T-xxx / gap ref
- refs: …

→ [decompose-…/index.md](decompose-…/index.md) — **после DECOMPOSE:** единственный трекер шагов (не дублировать s01…sNN здесь)

## Technology axiom (replace-not-wrap)

> **HARD** при смене machine boundary / structured validation. Канон: @.cursor/rules/shared/workflow-spec-first-replace.mdc  
> As-built читается для **sunset (что удалить)**, не как шаблон нового поведения.

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Pydantic / enum gate | JSON или YAML frontmatter | regex prose → enum |
| pydantic-ai extract | `Agent[OutputModel]` | free-text → regex |
| Sidecar schema vN | validate-on-write | dual path со старым parser |

Заполнить **до** HOW layout. DECOMPOSE → purge-step на каждый старый symbol из колонки FORBIDDEN.

## Продуктовая спека (WHAT)

> WHAT описывает пользовательскую проблему, ожидаемые outcomes и границы продукта. Не включать стек, имена модулей, API или детали реализации — они относятся к HOW.

## Product probe (office-hours lite)

> L3+ обязателен batch до WHAT (минимум ≥4 отвеченных вопросов для L3 без отдельного CLARIFY). L2 — optional/lite.  
> Скрытые допущения должны стать явными до DECOMPOSE. Не сокращать строки/комментарии ради telegraph-cap.

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe:** Какую реальную проблему решаем (не фичу)? | … | … |
| 2 | **Narrowest wedge:** Какой минимальный вариант проверит гипотезу? | … | … |
| 3 | **Pre-mortem:** Почему этот план может провалиться через месяц? | … | … |
| 4 | **Distribution/Adoption:** Как пользователи узнают/начнут использовать? | … | … |
| 5 | **Technical leverage:** Какую тяжелую часть можно выкинуть или заменить? | … | … |
| 6 | **Appetite check:** Стоит ли задача заявленных ресурсов/timebox? | … | … |

Min: для L3+ — минимум 4 заполненных вопроса.

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
5. Нет dual machine path regex+pydantic на одной границе (spec-first-replace).

Канон: @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc · @.cursor/rules/shared/workflow-spec-first-replace.mdc

## Техника / архитектура (HOW)

> HOW описывает техническую стратегию и границы реализации отдельно от WHAT.

- Стек и инфраструктура: …
- Модули, интеграции и контракты: …
- Ограничения реализации и наблюдаемость: …

## Eng review spine

> **L2+ обязательно** (согласовано с PLAN lean gates 8–10): data-flow + failure matrix + Review readiness. L3+ — полный spine. L1 — optional.  
> Секции не подлежат сокращению ради token-economy.

### Data flow (ASCII)

```text
[Actor] -> [Module A] -> [Module B] -> [Store/API]
         sync/async    retry?         fail-closed?
```

Min: ≥1 diagram, ≥3 hops, явные async/sync границы.

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| … | … | … | … | TM-001 |

Min: ≥5 rows; ≥1 row на external I/O или persistence если есть. Test matrix TM-IDs cross-link to ## QA consumes rows.

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | | |
| Failure coverage | | |
| Testability | | |

Min: самооценка 1–5 по трем измерениям engineering spine.

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

<a id="qa-consumes"></a>
## QA consumes (test plan)

> BACK QA: загружать **только эту секцию** (+ qa shard + diff). Не full plan.

### Scope under test

- Epic / surfaces: …
- Out of scope for QA: …

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | … | `.venv/bin/pytest …` | PASS / exit 0 | AC-1 |

Min: ≥3 P0 rows для L3; каждый AC+ plan должен иметь ≥1 TM row. TM-IDs cross-link to Failure matrix Test ID.

### Regression notes

- Flaky / ordering / env: …

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3: one of done | done \| skip+reason \| pending | link clarify or §Product probe |
| Eng review spine | L2+ | done \| pending | §Eng review spine filled |
| §0.11 counterparts (draft) | if external refs in HOW | done \| n/a \| pending | table or defer list |
| CREATIVE | if flagged | done \| n/a | link creative |
| qa_consumes draft | L2+ | done \| pending | §QA consumes ≥3 TM |
| Plan review batch | L2+ | done \| pending | §Plan review batch log |

**FINISH PLAN allowed:** no `pending` in Required rows for epic level.

## Plan review batch log

<!-- Принципы auto-resolve: prefer completeness · match existing patterns · reversible · defer ambiguous · escalate security → CRITICAL marker -->

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product (brainstorming) | … | … | … |
| Eng (architecture-patterns) | … | … | … |

## До DECOMPOSE (черновик нарезки)

Краткий outline фаз **без** checkbox-статусов (статусы появятся только в decompose index).  
После DECOMPOSE — этот блок сжать или удалить; детали → `sNN-*.yaml`.  
Brownfield: в конце очереди заложить `sNN-legacy-fallback-purge`.

## Appetite

> Бюджет эпика (Shape Up): **время** и **что вырезать первым**, не потолок числа `sNN`.  
> **FORBIDDEN:** лимит/circuit-breaker на число шагов decompose («стоп если >N sNN») — конфликтует с Maximal detail (дырка в coverage → добавить sNN; count в §нарезка — advisory floor).  
> Loop не форсирует эти поля.

| Поле | Значение / пример | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | Желаемый timebox (календарь), не cap нарезки |
| `cut_list` | `['optional UI polish', 'extra metrics']` | Что вырезать первым при превышении бюджета (scope), не «меньше sNN» |

## Следующий режим

→ BACK/FRONT DECOMPOSE | CREATIVE | IMPLEMENT
