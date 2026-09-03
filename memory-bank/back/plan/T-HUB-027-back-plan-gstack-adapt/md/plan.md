# [T-HUB-027 | back-plan-gstack-adapt] PLAN

**Дата:** 2026-08-30  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Research / refs:** сравнение gstack (Gary Tan) vs dev-hub workflow; T-HUB-010 CLARIFY/WHAT; gstack `docs/skills.md` (office-hours, plan-eng-review, autoplan, plan→QA)  
**Skills:** writing-plans · brainstorming · architecture-patterns · python-testing-patterns · grill-me (blockers only)

→ [T-HUB-027-back-plan-gstack-adapt/md/decompose-index.md](T-HUB-027-back-plan-gstack-adapt/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** перенести лучшие практики gstack в hub BACK PLAN **без** замены memory-bank / DECOMPOSE / loop — additive слой: product probe, eng spine в plan, test plan → QA, plan review batch, review readiness dashboard.
- **deps:** soft T-HUB-010 (CLARIFY + WHAT/HOW уже есть). Hard deps нет.
- **поверхность:** только dev-hub tooling — `.cursor/templates/`, `.cursor/rules/back_developer/`, `.cursor/rules/shared/workflow-clarify-core.mdc`, `.cursor/rules/back_developer/workflow-qa.mdc`, `.claude/skills/role-command/SKILL.md`, refs doc.
- **out of scope:** установка gstack slash-команд; FRONT/INTEG full parity (только явно помеченные зеркала); `/qa` browser Playwright (остаётся FRONT); замена DECOMPOSE на «plan = prompt»; GSD `.planning/` layout.

### Зафиксированные решения (brainstorming batch)

| Тема | Решение |
|------|---------|
| Product probe | **Office-hours lite** — 6 forcing questions; опциональный блок в CLARIFY и обязательный **batch-таблица** в L3+ PLAN если CLARIFY skip |
| Eng spine | Новые секции plan template: ASCII **data-flow**, **failure matrix**, **test matrix**; L3+ обязательны |
| QA bridge | Секция **`## QA consumes (test plan)`** в каждом L2+ plan; BACK QA `load_now` += plan `§QA consumes` only |
| Plan review batch | Шаг в `workflow-plan.mdc`: product → eng spine → auto-resolve defer; не отдельная slash-команда |
| Review readiness | Таблица в plan + gate FINISH PLAN: все required rows ≠ `pending` |
| Rating 0–10 | **Eng spine self-check** (3 строки: data-flow / failures / tests) — без interactive 0–10 как gstack design review |
| Multi-epic | **Out** — один эпик; FRONT plan mirror — follow-up если нужен |
| CREATIVE | нет |

### CREATIVE need

**нет**

---

## Цель

BACK PLAN на L2+ выдаёт plan, который (1) challenge'ит продукт до HOW, (2) фиксирует eng spine с диаграммами и failure modes, (3) несёт исполняемый test plan для QA без загрузки всего plan, (4) показывает review readiness перед DECOMPOSE, (5) проходит compact review batch за один PLAN-чат без 15–30 интерактивных пауз gstack.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как разработчик hub, я хочу product probe до WHAT, чтобы не планировать «calendar app» вместо реальной проблемы. | P0 | L3 PLAN без CLARIFY → в plan есть таблица Product probe с ≥4 заполненными строками или ссылка на clarify |
| US-002 | Как разработчик, я хочу eng spine (data-flow + failures + tests) в plan, чтобы скрытые допущения были видны до DECOMPOSE. | P0 | Новый plan L3 → секции с non-empty ASCII/bullet matrix |
| US-003 | Как BACK QA, я хочу test plan из plan без monolith load, чтобы проверять по матрице сценариев. | P0 | BACK QA session → `load_now` указывает plan `#qa-consumes`; qa yaml ссылается Test matrix IDs |
| US-004 | Как оператор loop, я хочу review readiness в plan FINISH, чтобы видеть готовность к DECOMPOSE одной таблицей. | P1 | FINISH PLAN → таблица Review readiness без `pending` в required rows |
| US-005 | Как разработчик, я хочу plan review batch в одном BACK PLAN, чтобы не гонять CEO/design/eng отдельными чатами. | P1 | workflow-plan step 2p documented; plan содержит `Plan review batch log` |

#### Acceptance Scenarios — US-001

- **Given:** `BACK PLAN` L3, CLARIFY не выполнялся, scope = новая feature
- **When:** agent заполняет plan
- **Then:** секция `## Product probe (office-hours lite)` с reframe + narrowest wedge + таблица 6 вопросов (answered или explicit defer)

#### Acceptance Scenarios — US-003

- **Given:** plan с `## QA consumes` и Test matrix TM-001…TM-00N
- **When:** `BACK QA` после IMPLEMENT
- **Then:** qa yaml поле `test_matrix_coverage: [TM-001, …]`; gate 1 загружает только anchor `#qa-consumes`

### Functional Requirements (FR-###)

- **FR-001:** `workflow-clarify-core.mdc` содержит подсекцию **Product probe (office-hours lite)** — 6 forcing questions (RU), правила batch vs sequential (CLARIFY ≤5 total включает product Q только если нет отдельного product pass в PLAN).
- **FR-002:** `.cursor/templates/clarify.md` — опциональная секция `## Product probe` (reframe, premises, narrowest wedge).
- **FR-003:** `.cursor/templates/plan.md` — секции: `Product probe`, `Eng review spine`, `QA consumes`, `Review readiness`, `Plan review batch log`.
- **FR-004:** Eng review spine: подсекции `Data flow (ASCII)`, `Failure matrix`, `Test matrix (plan-level)` с минимальными row counts (см. HOW).
- **FR-005:** `workflow-plan.mdc` — step **2p Plan review batch** после level fix; skills list дополнен явным eng pass; FINISH gate на Review readiness.
- **FR-006:** `workflow-qa.mdc` + `_lean/qa.mdc` — при epic QA: если plan содержит `#qa-consumes`, load `plan §QA consumes` (offset/grep), не full plan.
- **FR-007:** `memory-bank/back/plan/refs/gstack-adapt-027.md` — telegraph: что взяли / что отвергли из gstack.
- **FR-008:** `role-command/SKILL.md` — PLAN FINISH guard упоминает Review readiness + qa_consumes для L2+.
- **FR-009:** Legacy plans без новых секций остаются valid; gates применяются к **новым** PLAN после merge эпика.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 100% новых L3 BACK plan содержат Eng review spine | spot-check 1 plan post-IMPLEMENT | outcome |
| SC-002 | BACK QA может закрыть epic используя только qa_consumes + shards | qa yaml test_matrix_coverage | outcome |
| SC-003 | DECOMPOSE не дублирует test matrix целиком — ссылается `consumes: plan §QA consumes TM-xxx` | decompose sNN sample | buildable |

### Assumptions

- Hub workflow остаётся primary; gstack — reference, не runtime dependency.
- L1 PLAN (micro task) — Product probe и Eng spine **optional** (workflow gate: level ≥ L2 required).

### Clarifications

- Session: 2026-08-30 — chat comparison gstack vs dev-hub; решения в таблице выше.
- gstack `/autoplan` → наш **Plan review batch** (batch, без отдельной команды).
- gstack design 0–10 → **out** для BACK (FRONT follow-up).

### [НУЖНО УТОЧНИТЬ]

- n/a (решения зафиксированы в batch table)

---

## AC

1. `.cursor/templates/plan.md` содержит все 5 новых секций с комментариями min rows.
2. `workflow-plan.mdc` содержит step 2p + FINISH readiness gate.
3. `workflow-clarify-core.mdc` содержит 6 forcing questions + правило квоты с CLARIFY.
4. `workflow-qa.mdc` + `_lean/qa.mdc` — load rule для `#qa-consumes`.
5. Refs doc `gstack-adapt-027.md` существует.
6. Dry-run: exemplar fragment plan (в refs или QA step) показывает заполненный Review readiness = CLEARED.
7. `rg 'QA consumes|Review readiness|Product probe|Eng review spine' .cursor/` → hits в template + workflow.

### AC−

1. Не устанавливать gstack / не добавлять `/office-hours` slash как канон hub.
2. Не удалять DECOMPOSE / не схлопывать plan+implement в один prompt-file.
3. Не требовать browser QA в BACK QA workflow.
4. Не ломать §0.0 SUSPENSION GUARD — новые секции plan **не** telegraph-cap.
5. Не делать interactive AskUserQuestion one-by-one обязательным в PLAN (batch table достаточно).

### AC− (brownfield)

1. Старые `plan-*.md` без новых секций — не FAIL при QA/DECOMPOSE.
2. Additive-only к templates/rules — no sunset A/B/C code paths.

---

## Техника / архитектура (HOW)

### Стек

Docs/rules only. Verification: `rg`, dry-run checklist, optional pytest если добавят тесты на `loop/` validators (out of scope unless trivial).

### Компоненты / файлы

| Файл | Действие |
|------|----------|
| `.cursor/templates/plan.md` | Edit — 5 секций + anchor `#qa-consumes` |
| `.cursor/templates/clarify.md` | Edit — Product probe block |
| `.cursor/rules/shared/workflow-clarify-core.mdc` | Edit — office-hours lite 6 Q |
| `.cursor/rules/back_developer/workflow-plan.mdc` | Edit — step 2p, readiness FINISH, skills note |
| `.cursor/rules/back_developer/isolation_rules/_lean/plan.mdc` | Edit — gates 8–10 readiness + eng spine |
| `.cursor/rules/back_developer/workflow-qa.mdc` | Edit — load qa_consumes |
| `.cursor/rules/back_developer/isolation_rules/_lean/qa.mdc` | Edit — gate qa_consumes |
| `.cursor/rules/shared/finish-doc-router.mdc` | Edit — PLAN load_now hint qa_consumes |
| `memory-bank/back/plan/refs/gstack-adapt-027.md` | Create — adapt note |
| `.claude/skills/role-command/SKILL.md` | Edit — PLAN FINISH guards (mirror `.agents` if exists) |

**Optional mirror (не блокирует AC):** однострочная отсылка в `front_developer/workflow-plan.mdc` «BACK parity: product/QA consumes — см. T-HUB-027».

### Eng review spine — канон содержания (template contract)

```markdown
## Eng review spine

> L3+ обязательно. L2 — data-flow + failure matrix; test matrix может ссылаться на plan §тест-стратегия.

### Data flow (ASCII)

```text
[Actor] -> [Module A] -> [Module B] -> [Store/API]
         sync/async    retry?         fail-closed?
```

Min: ≥1 diagram, ≥3 hops, явные async/sync границы.

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| … | … | … | … | TM-… |

Min: ≥5 rows; ≥1 row на external I/O или persistence если есть.

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | | |
| Failure coverage | | |
| Testability | | |
```

### QA consumes — канон (anchor `#qa-consumes`)

```markdown
## QA consumes (test plan)

> BACK QA: загружать **только эту секцию** (+ qa shard + diff). Не full plan.

### Scope under test

- Epic / surfaces: …
- Out of scope for QA: …

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | … | `.venv/bin/pytest …` | PASS / exit 0 | AC-1 |

Min: ≥3 P0 rows для L3; каждый AC+ plan должен иметь ≥1 TM row.

### Regression notes

- Flaky / ordering / env: …
```

### Review readiness — канон

```markdown
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
```

### Plan review batch log — канон

```markdown
## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product (brainstorming) | … | … | … |
| Eng (architecture-patterns) | … | … | … |
```

Принципы auto-resolve (из gstack autoplan, encoded): prefer completeness · match existing patterns · reversible · defer ambiguous · escalate security → CRITICAL marker.

### Product probe — 6 forcing questions (RU)

1. **Demand reality:** Кто конкретно (роль/ситуация) получит value? Назови одного представителя, не «пользователи».
2. **Status quo:** Как они решают проблему сегодня без этой фичи?
3. **Desperate specificity:** Один реальный пример боли (событие, не гипотеза).
4. **Narrowest wedge:** Минимальный shippable slice за один IMPLEMENT цикл?
5. **Observation & surprise:** Что пользователь скажет «ого» после первого использования?
6. **Future-fit:** Это усиливает или отвлекает от текущего roadmap hub/product?

Output: **Reframe** (1–2 предложения) + **Premises** (3–5 falsifiable) + **Recommended wedge**.

### Data flow — exemplar (hub epic)

```text
Developer -> BACK PLAN -> plan.md (WHAT+spine+qa_consumes)
          -> BACK DECOMPOSE -> sNN.yaml (consumes TM-ids)
          -> BACK IMPLEMENT -> code + pytest
          -> BACK QA -> load qa_consumes only -> qa.yaml
          -> loop finalize-step
```

### §0.11 counterparts (draft)

| External ref in plan/HOW | Code/script counterpart | Verify in QA |
|--------------------------|---------------------------|--------------|
| `workflow-plan.mdc` step 2p | `.cursor/rules/back_developer/workflow-plan.mdc` | rg step 2p |
| `#qa-consumes` anchor | `.cursor/templates/plan.md` | rg qa-consumes |
| BACK QA load rule | `workflow-qa.mdc` gate | dry-run doc |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| n/a | — | greenfield |

### B. Entrypoints / deploy

| n/a | — | greenfield |

### C. Fallbacks / soft-fail

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| QA читает «plan целиком при неясном AC» без попытки qa_consumes | Сначала `plan §QA consumes`; full plan §N только если TM missing | delete in-epic (process) |

---

## Тест-стратегия

- **Unit/API:** не обязателен для rules-only эпика.
- **QA эпика (s06):** checklist AC+ через `rg`; dry-run BACK QA load path на fixture plan fragment; reviewer на diff rules.
- **Regression:** T-HUB-010 clarify flows не сломаны — `rg CLARIFY` + sample clarify template parse.

---

## Риски

| Риск | Митигация |
|------|-----------|
| Plan template раздуется | Min rows + self-check; L1 exempt |
| Дубль brainstorming / grill-me | Product probe = structured 6Q; brainstorming batch в PLAN review log |
| QA не находит anchor | Explicit `#qa-consumes` + gate FAIL if epic plan L2+ без section post-cutoff date |
| Token load on PLAN | Batch в одном чате; IMPLEMENT still lean shard |

---

## До DECOMPOSE

→ [T-HUB-027-back-plan-gstack-adapt/yaml/decompose-index.yaml](T-HUB-027-back-plan-gstack-adapt/yaml/decompose-index.yaml) — **единственный трекер** (s01–s08). Детали шагов — только в `sNN-*.yaml`.

CREATIVE: нет  
**Next mode:** → BACK IMPLEMENT s01

---

## Следующий режим

→ **BACK IMPLEMENT** [T-HUB-027-back-plan-gstack-adapt/yaml/steps/s01-clarify-product-probe.yaml](T-HUB-027-back-plan-gstack-adapt/yaml/steps/s01-clarify-product-probe.yaml)
